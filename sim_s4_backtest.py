from __future__ import annotations

from datetime import datetime, timezone, timedelta

import MetaTrader5 as mt5

import config
import hhll_swing
from sim_lifecycle import (
    fill_pdfiboplus_round1,
    fill_pdfiboplus_round2,
    fill_trend_recheck_round1,
    fill_trend_recheck_round2,
    limit_guard_cancel,
    limit_sweep_followup_s8,
    opposite_order_apply,
    pd_cancel_event,
    pending_pdfiboplus_round2,
    pending_trend_check_round1,
    pending_trend_check_round2,
    SimSLGuard,
    fill_rsi_recheck,
    trail_sl_apply,
    trend_cancel_event,
    pdfiboplus_applies,
    pdfiboplus_in_zone,
)
from strategy4 import strategy_4, _find_prev_pivot_swing_high, _find_prev_pivot_swing_low


SYMBOL = config.SYMBOL
SINCE = datetime(2026, 5, 24, 0, 0, 0, tzinfo=timezone.utc)
VOLUME = 0.01
PRICE_TO_USD = 100 * VOLUME

UTC = timezone.utc
TZ_OFF = getattr(config, "TZ_OFFSET", 7)
SRV_TZ = getattr(config, "MT5_SERVER_TZ", 0)

TF_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}

TF_EXTRA_BARS = {
    "M1": 18000,
    "M5": 900,
    "M15": 500,
    "M30": 300,
    "H1": 220,
    "H4": 120,
    "D1": 80,
}
TF_SECONDS = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "M30": 1800,
    "H1": 3600,
    "H4": 14400,
    "D1": 86400,
}


def to_bkk(ts: int) -> datetime:
    return datetime.fromtimestamp(int(ts), tz=UTC) + timedelta(hours=TZ_OFF - SRV_TZ)


def profit(price_diff: float) -> float:
    return round(float(price_diff) * PRICE_TO_USD, 2)


def s4_runtime_feature_coverage() -> list[dict]:
    return [
        {
            "name": "S4 significant FVG detect",
            "config_on": bool(config.active_strategies.get(4, False)),
            "runtime": "apply",
            "replay": "apply",
            "note": "Replay injects historical HHLL cache and calls shared strategy4.strategy_4(..., tf=tf_name)",
        },
        {
            "name": "Pending limit lifecycle",
            "config_on": True,
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay models pending fill and fixed SL/TP with bar high/low",
        },
        {
            "name": "PD Fibo Plus",
            "config_on": getattr(config, "PDFIBOPLUS_ENABLED", False),
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay applies pending and fill round1/round2 gates",
        },
        {
            "name": "Limit Trend/Fill Trend Recheck",
            "config_on": getattr(config, "LIMIT_TREND_RECHECK", False),
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay applies pending approach and fill round1/round2 per-TF HHLL trend",
        },
        {
            "name": "RSI Fill Recheck",
            "config_on": getattr(config, "PENDING_RSI_RECHECK_ENABLED", False),
            "runtime": "apply",
            "replay": "ready",
            "note": "Replay supports mode1/mode2/mode3 when enabled",
        },
        {
            "name": "Trail/Opposite/Limit Guard",
            "config_on": getattr(config, "TRAIL_SL_ENABLED", False) or getattr(config, "OPPOSITE_ORDER_ENABLED", False) or getattr(config, "LIMIT_GUARD", False),
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay applies Limit Guard, Opposite Order, engulf/reversal/Focus/trend-override Trail SL, and SL Guard/Group retry/unblock baseline",
        },
        {
            "name": "Limit Sweep follow-up S8",
            "config_on": getattr(config, "LIMIT_SWEEP", False),
            "runtime": "apply",
            "replay": "ready",
            "note": "Replay can close swept positions and queue S8 follow-up orders when enabled",
        },
    ]


def s4_unreplayed_active_features() -> list[dict]:
    return [
        item for item in s4_runtime_feature_coverage()
        if item["config_on"] and item["replay"] == "gap"
    ]


def _as_records(rates) -> list[dict]:
    return sorted(
        [{name: r[name] for name in rates.dtype.names} for r in rates],
        key=lambda r: int(r["time"]),
    )


def _fetch_rates(tf_name: str, tf_val: int, range_end_utc: datetime | None = None):
    total = TF_EXTRA_BARS.get(tf_name, 500) + 8000
    if range_end_utc is None:
        return mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, total)

    pad_bars = max(
        120,
        int(getattr(config, "HHLL_LOOKBACK", 500) or 500)
        + int(getattr(config, "HHLL_LEFT", 5) or 5)
        + int(getattr(config, "HHLL_RIGHT", 5) or 5)
        + int(getattr(config, "TF_LOOKBACK", {}).get(tf_name, getattr(config, "SWING_LOOKBACK", 20)) or 20)
        + 20,
    )
    start_utc = SINCE - timedelta(seconds=TF_SECONDS.get(tf_name, 60) * pad_bars)
    return mt5.copy_rates_range(SYMBOL, tf_val, start_utc, range_end_utc)


def _entry_already_passed(result: dict, signal_bar: dict) -> bool:
    entry = float(result.get("entry", 0.0) or 0.0)
    close = float(signal_bar["close"])
    signal = result.get("signal")
    if signal == "BUY":
        return close <= entry
    if signal == "SELL":
        return close >= entry
    return False


def _close_row(trade: dict, reason: str, price: float, close_time: datetime) -> dict:
    if trade["signal"] == "BUY":
        pnl = profit(float(price) - float(trade["entry"]))
    else:
        pnl = profit(float(trade["entry"]) - float(price))
    return {
        **trade,
        "close_time": close_time,
        "close_type": reason,
        "close_price": round(float(price), 2),
        "pnl": pnl,
        "profit": pnl,
        "reason": reason,
    }


def _pending_from_result(result: dict, tf_name: str, detect_bar: dict) -> dict:
    signal = result["signal"]
    return {
        "sid": 4,
        "tf": tf_name,
        "signal": signal,
        "side": signal,
        "pattern": result.get("pattern", "S4 Significant FVG"),
        "entry": round(float(result["entry"]), 2),
        "sl": round(float(result["sl"]), 2),
        "tp": round(float(result["tp"]), 2),
        "detect_time": to_bkk(detect_bar["time"]),
        "detect_time_raw": int(detect_bar["time"]),
    }


def _pd_precreate_check(order: dict, scan_rates: list[dict], tf_name: str) -> dict:
    sid = int(order.get("sid", 0) or 0)
    signal = order.get("signal") or order.get("side")
    if not pdfiboplus_applies(sid) or signal not in ("BUY", "SELL"):
        return {"status": "skip"}
    lookback = int(getattr(config, "TF_LOOKBACK", {}).get(tf_name, getattr(config, "SWING_LOOKBACK", 100)) or 100)
    left = max(1, int(getattr(config, "SWING_PIVOT_LEFT", 15) or 15))
    right = max(1, int(getattr(config, "SWING_PIVOT_RIGHT", 10) or 10))
    sh = _find_prev_pivot_swing_high(scan_rates, lookback=lookback, left=left, right=right)
    sl = _find_prev_pivot_swing_low(scan_rates, lookback=lookback, left=left, right=right)
    if not sh or not sl:
        return {"status": "wait", "reason": "PD pre-create no scanner swing data"}
    high = float(sh.get("price", 0.0) or 0.0)
    low = float(sl.get("price", 0.0) or 0.0)
    entry = float(order.get("entry", 0.0) or 0.0)
    if high <= low or entry <= 0:
        return {"status": "wait", "reason": "PD pre-create invalid scanner swing range"}
    ok = pdfiboplus_in_zone(entry, signal, high, low, sid=sid)
    if ok:
        return {"status": "pass", "pd_h": round(high, 2), "pd_l": round(low, 2)}
    return {"status": "fail", "reason": "PD pre-create scanner swing fail", "pd_h": round(high, 2), "pd_l": round(low, 2)}


def _build_historical_hhll_data(rates: list[dict]) -> dict:
    lb = int(getattr(config, "HHLL_LEFT", 5) or 5)
    rb = int(getattr(config, "HHLL_RIGHT", 5) or 5)
    lookback = int(getattr(config, "HHLL_LOOKBACK", 500) or 500)
    window = rates[-(lookback + lb + rb + 5):]
    if len(window) < lb + rb + 10:
        return {}

    zz = hhll_swing._build_zz(window, lb, rb)
    if len(zz) < 5:
        return {}

    buckets = {"HH": None, "HL": None, "LH": None, "LL": None}
    prev_buckets = {"HH": None, "HL": None, "LH": None, "LL": None}
    structure = []
    for k in range(len(zz)):
        label = hhll_swing._classify_pt(zz, k)
        if not label:
            continue
        pt = {"price": zz[k]["price"], "time": zz[k]["time"], "label": label}
        prev_buckets[label] = buckets[label]
        buckets[label] = pt
        structure.append(label)

    return {
        "hh": buckets["HH"],
        "hl": buckets["HL"],
        "lh": buckets["LH"],
        "ll": buckets["LL"],
        "prev_hh": prev_buckets["HH"],
        "prev_hl": prev_buckets["HL"],
        "prev_lh": prev_buckets["LH"],
        "prev_ll": prev_buckets["LL"],
        "last_label": structure[-1] if structure else "",
        "structure": list(reversed(structure[-6:])),
    }


def _strategy_4_historical(scan_rates: list[dict], full_rates: list[dict], tf_name: str) -> dict:
    old_data = hhll_swing._hhll_data.get(tf_name)
    hist_data = _build_historical_hhll_data(full_rates)
    if hist_data:
        hhll_swing._hhll_data[tf_name] = hist_data
    try:
        return strategy_4(scan_rates, tf=tf_name if hist_data else "")
    finally:
        if old_data is None:
            hhll_swing._hhll_data.pop(tf_name, None)
        else:
            hhll_swing._hhll_data[tf_name] = old_data


def _strategy_4_with_hhll(scan_rates: list[dict], hist_data: dict, tf_name: str) -> dict:
    old_data = hhll_swing._hhll_data.get(tf_name)
    if hist_data:
        hhll_swing._hhll_data[tf_name] = hist_data
    try:
        return strategy_4(scan_rates, tf=tf_name if hist_data else "")
    finally:
        if old_data is None:
            hhll_swing._hhll_data.pop(tf_name, None)
        else:
            hhll_swing._hhll_data[tf_name] = old_data


def _fill_trade(order: dict, bar: dict) -> dict:
    return {
        **order,
        "entry_time": to_bkk(bar["time"]),
        "entry_time_raw": int(bar["time"]),
        "close_type": "OPEN",
    }


def backtest_tf(tf_name: str, tf_val: int, range_end_utc: datetime | None = None) -> list[dict]:
    rates = _fetch_rates(tf_name, tf_val, range_end_utc=range_end_utc)
    if rates is None or len(rates) < 120:
        return []
    symbol_info = mt5.symbol_info(SYMBOL)
    point = float(getattr(symbol_info, "point", 0.01) or 0.01)
    spread = float(getattr(symbol_info, "spread", 0) or 0) * point
    bars = _as_records(rates)
    trail_rates_by_tf = {}
    for trail_tf in list(getattr(config, "TRAIL_GROUPS", {}).get(tf_name, [tf_name])):
        trail_val = TF_MAP.get(trail_tf)
        if trail_val is None:
            continue
        raw_trail = _fetch_rates(trail_tf, trail_val, range_end_utc=range_end_utc)
        if raw_trail is not None:
            trail_rates_by_tf[trail_tf] = _as_records(raw_trail)
    since_ts = int(SINCE.timestamp())
    start_idx = max(80, next((i for i, r in enumerate(bars) if int(r["time"]) >= since_ts), 80))
    strategy_window = max(80, int(getattr(config, "TF_LOOKBACK", {}).get(tf_name, getattr(config, "SWING_LOOKBACK", 20)) or 20) + 6)

    trades: list[dict] = []
    pending: list[dict] = []
    open_trades: list[dict] = []
    fired: set[tuple] = set()
    sl_guard = SimSLGuard(point)
    trail_focus_state: dict = {}

    for i in range(start_idx, len(bars)):
        bar = bars[i]
        bt = to_bkk(bar["time"])
        h = float(bar["high"])
        l = float(bar["low"])
        full_rates = bars[:i + 1]
        hist_data = _build_historical_hhll_data(full_rates)

        still_pending = []
        for order in pending:
            if sl_guard.near_blocked(tf_name, order["signal"], float(order["entry"]), bar, full_rates):
                trades.append(trend_cancel_event(order, bt, "SL Guard active near entry"))
                continue
            lg = limit_guard_cancel(order, open_trades, bar, point)
            if lg.get("status") == "fail":
                trades.append(trend_cancel_event(order, bt, lg.get("reason", "Limit Guard cancel")))
                continue
            pd_pending2 = pending_pdfiboplus_round2(order, full_rates)
            if pd_pending2.get("status") == "fail":
                trades.append(pd_cancel_event(order, bt))
                continue
            tr_pending2 = pending_trend_check_round2(order, full_rates)
            if tr_pending2.get("status") == "fail":
                trades.append(trend_cancel_event(order, bt, tr_pending2.get("reason", "Pending Trend Check round2 fail")))
                continue
            tr_pending = pending_trend_check_round1(order, full_rates, bar, point)
            if tr_pending.get("status") == "fail":
                trades.append(trend_cancel_event(order, bt, tr_pending.get("reason", "Pending Trend Check round1 fail")))
                continue
            if order["signal"] == "BUY" and l <= float(order["entry"]):
                trade = _fill_trade(order, bar)
                pd = fill_pdfiboplus_round1(trade, full_rates)
                if pd.get("status") == "fail":
                    trades.append(_close_row(trade, "PD_FILL_FAIL", float(bar["close"]), bt))
                else:
                    rsi = fill_rsi_recheck(trade, full_rates)
                    if rsi.get("status") == "fail":
                        trades.append(_close_row(trade, "RSI_FAIL", float(bar["close"]), bt))
                    else:
                        tr = fill_trend_recheck_round1(trade, full_rates)
                        if tr.get("status") == "fail":
                            trades.append(_close_row(trade, "TREND_FAIL", float(bar["close"]), bt))
                        else:
                            open_trades.append(trade)
            elif order["signal"] == "SELL" and h >= float(order["entry"]):
                trade = _fill_trade(order, bar)
                pd = fill_pdfiboplus_round1(trade, full_rates)
                if pd.get("status") == "fail":
                    trades.append(_close_row(trade, "PD_FILL_FAIL", float(bar["close"]), bt))
                else:
                    rsi = fill_rsi_recheck(trade, full_rates)
                    if rsi.get("status") == "fail":
                        trades.append(_close_row(trade, "RSI_FAIL", float(bar["close"]), bt))
                    else:
                        tr = fill_trend_recheck_round1(trade, full_rates)
                        if tr.get("status") == "fail":
                            trades.append(_close_row(trade, "TREND_FAIL", float(bar["close"]), bt))
                        else:
                            open_trades.append(trade)
            else:
                still_pending.append(order)
        pending = still_pending

        opposite_closes = opposite_order_apply(open_trades, pending, bar, spread)
        opposite_close_ids = {id(trade) for trade, _ in opposite_closes}
        guard_activated_sides = []
        still_open = []
        for trade in open_trades:
            if id(trade) in opposite_close_ids:
                trades.append(_close_row(trade, "OPPOSITE_CLOSE", float(bar["close"]), bt))
                continue
            sweep = limit_sweep_followup_s8(trade, full_rates, pending, bar, bars[i - 1] if i > 0 else None, tf_name)
            if sweep.get("status") == "close":
                row = _close_row(trade, "LIMIT_SWEEP", float(bar["close"]), bt)
                trades.append(row)
                if sl_guard.record_close(tf_name, trade["signal"], row["close_type"], row["pnl"], full_rates):
                    guard_activated_sides.append(trade["signal"])
                new_order = sweep.get("new_order")
                if new_order:
                    new_order["detect_time"] = to_bkk(new_order["detect_time_raw"])
                    pending.append(new_order)
                continue
            pd2 = fill_pdfiboplus_round2(trade, full_rates)
            if pd2.get("status") == "fail":
                trades.append(_close_row(trade, "PD_FILL_FAIL", float(bar["close"]), bt))
                continue
            tr2 = fill_trend_recheck_round2(trade, full_rates)
            if tr2.get("status") == "fail":
                trades.append(_close_row(trade, "TREND_FAIL", float(bar["close"]), bt))
                continue
            trail_sl_apply(
                trade, trail_rates_by_tf, int(bar["time"]), tf_name,
                open_trades=open_trades, pending=pending, bar=bar,
                point=point, spread=spread, focus_state=trail_focus_state,
            )
            if trade["signal"] == "BUY":
                if l <= float(trade["sl"]):
                    row = _close_row(trade, "SL", trade["sl"], bt)
                    trades.append(row)
                    if sl_guard.record_close(tf_name, trade["signal"], row["close_type"], row["pnl"], full_rates):
                        guard_activated_sides.append(trade["signal"])
                    continue
                if h >= float(trade["tp"]):
                    row = _close_row(trade, "TP", trade["tp"], bt)
                    trades.append(row)
                    sl_guard.record_close(tf_name, trade["signal"], row["close_type"], row["pnl"], full_rates)
                    continue
            else:
                if h >= float(trade["sl"]):
                    row = _close_row(trade, "SL", trade["sl"], bt)
                    trades.append(row)
                    if sl_guard.record_close(tf_name, trade["signal"], row["close_type"], row["pnl"], full_rates):
                        guard_activated_sides.append(trade["signal"])
                    continue
                if l <= float(trade["tp"]):
                    row = _close_row(trade, "TP", trade["tp"], bt)
                    trades.append(row)
                    sl_guard.record_close(tf_name, trade["signal"], row["close_type"], row["pnl"], full_rates)
                    continue
            still_open.append(trade)
        if guard_activated_sides and getattr(config, "SL_GUARD_CLOSE_ON_ACTIVATE", True):
            active_sides = set(guard_activated_sides)
            kept_open = []
            for trade in still_open:
                if trade["signal"] in active_sides:
                    trades.append(_close_row(trade, "SL_GUARD_CLOSE", float(bar["close"]), bt))
                else:
                    kept_open.append(trade)
            still_open = kept_open
            kept_pending = []
            for order in pending:
                if order["signal"] in active_sides:
                    trades.append(trend_cancel_event(order, bt, "SL Guard activated"))
                else:
                    kept_pending.append(order)
            pending = kept_pending
        open_trades = still_open

        for retry_order in sl_guard.pop_retry_orders(tf_name, full_rates, bar):
            retry_order["detect_time"] = to_bkk(retry_order["detect_time_raw"])
            duplicate_pending = any(
                p["signal"] == retry_order.get("signal")
                and abs(float(p["entry"]) - float(retry_order.get("entry", 0.0) or 0.0)) <= 0.01
                and abs(float(p["sl"]) - float(retry_order.get("sl", 0.0) or 0.0)) <= 0.01
                and abs(float(p["tp"]) - float(retry_order.get("tp", 0.0) or 0.0)) <= 0.01
                for p in pending
            )
            if not duplicate_pending:
                pending.append(retry_order)

        scan_rates = bars[max(0, i - strategy_window + 1):i + 1]
        result = _strategy_4_with_hhll(scan_rates, hist_data, tf_name)
        if result.get("signal") not in ("BUY", "SELL"):
            continue
        if _entry_already_passed(result, bar):
            continue
        key = (
            int(bar["time"]),
            result.get("signal"),
            round(float(result.get("entry", 0.0) or 0.0), 2),
            round(float(result.get("sl", 0.0) or 0.0), 2),
            round(float(result.get("tp", 0.0) or 0.0), 2),
            str(result.get("pattern", "")),
        )
        if key in fired:
            continue
        fired.add(key)
        order = _pending_from_result(result, tf_name, bar)
        if sl_guard.is_blocked(tf_name, order["signal"], full_rates):
            sl_guard.record_blocked_order(tf_name, order, int(bar["time"]))
            trades.append(trend_cancel_event(order, order["detect_time"], "SL Guard blocked new LIMIT"))
            continue
        pd = _pd_precreate_check(order, scan_rates, tf_name)
        if pd.get("status") == "fail":
            trades.append(pd_cancel_event(order, order["detect_time"]))
            continue
        pending.append(order)

    for order in pending:
        trades.append({
            **order,
            "entry_time": order["detect_time"],
            "entry_time_raw": order["detect_time_raw"],
            "close_time": None,
            "close_price": None,
            "close_type": "OPEN_PENDING",
            "pnl": 0.0,
            "profit": 0.0,
        })
    for trade in open_trades:
        trades.append({
            **trade,
            "close_time": None,
            "close_price": None,
            "close_type": "OPEN",
            "pnl": 0.0,
            "profit": 0.0,
        })
    return trades
