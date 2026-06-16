from __future__ import annotations

from datetime import datetime, timezone, timedelta

import MetaTrader5 as mt5

import config
import hhll_swing
import sim_s1_backtest
import sim_s2_backtest
import sim_s3_backtest
import sim_s4_backtest
import sim_s5_backtest
import sim_s8_backtest
from strategy1 import strategy_1
from strategy2 import strategy_2
from strategy3 import strategy_3
from strategy4 import strategy_4
from strategy5 import strategy_5
from strategy8 import strategy_8
from sim_lifecycle import (
    fill_pdfiboplus_round1,
    fill_pdfiboplus_round2,
    fill_rsi_recheck,
    fill_trend_recheck_round1,
    fill_trend_recheck_round2,
    limit_guard_cancel,
    limit_sweep_followup_s8,
    opposite_order_apply,
    pd_cancel_event,
    pending_pdfiboplus_round1,
    pending_pdfiboplus_round2,
    pending_trend_check_round1,
    pending_trend_check_round2,
    SimSLGuard,
    trail_sl_apply,
    trend_cancel_event,
)


SYMBOL = config.SYMBOL
UTC = timezone.utc
TZ_OFF = getattr(config, "TZ_OFFSET", 7)
SRV_TZ = getattr(config, "MT5_SERVER_TZ", 0)
VOLUME = 0.01
PRICE_TO_USD = 100 * VOLUME

TF_MAP = sim_s8_backtest.TF_MAP
TF_EXTRA_BARS = {
    tf: max(
        sim_s1_backtest.TF_EXTRA_BARS.get(tf, 0),
        sim_s2_backtest.TF_EXTRA_BARS.get(tf, 0),
        sim_s3_backtest.TF_EXTRA_BARS.get(tf, 0),
        sim_s4_backtest.TF_EXTRA_BARS.get(tf, 0),
        sim_s5_backtest.TF_EXTRA_BARS.get(tf, 0),
        sim_s8_backtest.TF_EXTRA_BARS.get(tf, 0),
    )
    for tf in TF_MAP
}
SINCE = min(
    sim_s1_backtest.SINCE,
    sim_s2_backtest.SINCE,
    sim_s3_backtest.SINCE,
    sim_s4_backtest.SINCE,
    sim_s5_backtest.SINCE,
    sim_s8_backtest.SINCE,
)
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


def _build_historical_hhll_data(rates: list[dict]) -> dict:
    return sim_s8_backtest._build_historical_hhll_data(rates)


def _call_with_hhll(tf_name: str, hist_data: dict, func, *args, **kwargs) -> dict:
    old_data = hhll_swing._hhll_data.get(tf_name)
    if hist_data:
        hhll_swing._hhll_data[tf_name] = hist_data
    try:
        return func(*args, **kwargs)
    finally:
        if old_data is None:
            hhll_swing._hhll_data.pop(tf_name, None)
        else:
            hhll_swing._hhll_data[tf_name] = old_data


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


def _pending_from_result(result: dict, tf_name: str, detect_bar: dict, sid: int) -> dict:
    if result.get("_prebuilt_order"):
        return dict(result["_prebuilt_order"])

    signal = result["signal"]
    row = {
        "sid": sid,
        "tf": tf_name,
        "signal": signal,
        "side": signal,
        "pattern": result.get("pattern", f"S{sid}"),
        "entry": round(float(result["entry"]), 2),
        "sl": round(float(result["sl"]), 2),
        "tp": round(float(result["tp"]), 2),
        "detect_time": to_bkk(detect_bar["time"]),
        "detect_time_raw": int(detect_bar["time"]),
    }
    if sid == 1:
        row.update({
            "cancel_bars": int(result.get("cancel_bars", 0) or 0),
            "s1_zone_meta": result.get("s1_zone_meta") or {},
        })
    if sid == 2:
        row.update({
            "gap_bot": round(float(result.get("gap_bot", 0.0) or 0.0), 2),
            "gap_top": round(float(result.get("gap_top", 0.0) or 0.0), 2),
            "final_gap_bot": round(float(result.get("gap_bot", 0.0) or 0.0), 2),
            "final_gap_top": round(float(result.get("gap_top", 0.0) or 0.0), 2),
            "c3_type": result.get("c3_type", ""),
            "cancel_bars": 1 if result.get("c3_type") == "ปฏิเสธราคา" else 0,
        })
    if sid == 3 and result.get("source_candle_time"):
        row.update({
            "source_candle_time": int(result.get("source_candle_time", 0) or 0),
            "marubozu_source": result.get("marubozu_source", "marubozu"),
        })
    if sid == 8:
        row.update({
            "intended_sl": row["sl"],
            "sl_armed": False,
            "swing_price": float(result.get("swing_price", 0.0) or 0.0),
            "swing_bar_time": int(result.get("swing_bar_time", 0) or 0),
        })
    return row


def _fill_trade(order: dict, bar: dict) -> dict:
    row = {
        **order,
        "entry_time": to_bkk(bar["time"]),
        "entry_time_raw": int(bar["time"]),
        "close_type": "OPEN",
    }
    if int(order.get("sid", 0) or 0) == 8:
        sl_armed = bool(order.get("sl_armed"))
        if not sl_armed and getattr(config, "DELAY_SL_MODE", "off") == "off":
            sl_armed = True
        row["sl_armed"] = sl_armed
    return row


def _duplicate_pending(pending: list[dict], order: dict) -> bool:
    for p in pending:
        if int(p.get("sid", 0) or 0) != int(order.get("sid", 0) or 0):
            continue
        if p.get("signal") != order.get("signal"):
            continue
        if abs(float(p.get("entry", 0.0) or 0.0) - float(order.get("entry", 0.0) or 0.0)) > 0.01:
            continue
        if abs(float(p.get("sl", 0.0) or 0.0) - float(order.get("sl", 0.0) or 0.0)) > 0.01:
            continue
        if abs(float(p.get("tp", 0.0) or 0.0) - float(order.get("tp", 0.0) or 0.0)) > 0.01:
            continue
        return True
    return False


def _scan_signals(
    strategies: set[int],
    scan_rates: list[dict],
    full_rates: list[dict],
    hist_data: dict,
    tf_name: str,
    bt: datetime,
    bar: dict,
    tf_secs: int,
    fallback_start: dict,
    maru_pending: dict,
) -> list[tuple[int, dict]]:
    signals: list[tuple[int, dict]] = []
    if 1 in strategies:
        r1 = strategy_1(full_rates, tf=tf_name)
        if r1.get("signal") in ("BUY", "SELL"):
            signals.append((1, r1))
    if 2 in strategies:
        r2 = strategy_2(full_rates, tf=tf_name)
        if r2.get("signal") == "FVG_DETECTED":
            fvg = r2.get("fvg") or {}
            signal = fvg.get("signal")
            if signal in ("BUY", "SELL") and sim_s2_backtest._s2_confirm_ok(
                full_rates, signal, tf_name, tf_secs, int(bar["time"]), fallback_start
            ):
                tp = sim_s2_backtest._calc_tp(full_rates, signal, float(fvg["entry"]), float(fvg["sl"]), tf_name)
                signals.append((2, {
                    "signal": signal,
                    "pattern": fvg.get("pattern", "S2 FVG"),
                    "entry": fvg.get("entry"),
                    "sl": fvg.get("sl"),
                    "tp": tp,
                    "gap_bot": fvg.get("gap_bot", 0.0),
                    "gap_top": fvg.get("gap_top", 0.0),
                    "c3_type": fvg.get("c3_type", ""),
                }))
    if 3 in strategies:
        for key, mp in list(maru_pending.items()):
            if int(bar["time"]) <= int(mp.get("candle_time", 0) or 0):
                continue
            bull_next = float(bar["close"]) > float(bar["open"])
            direction = mp.get("direction")
            color_ok = (direction == "BUY" and bull_next) or (direction == "SELL" and not bull_next)
            if color_ok and sim_s3_backtest._confirm_ok(full_rates, direction, tf_name, tf_secs, int(bar["time"]), fallback_start):
                signals.append((3, {"_prebuilt_order": sim_s3_backtest._pending_from_maru(mp, tf_name, bar)}))
            maru_pending.pop(key, None)

        r3 = strategy_3(full_rates)
        mp = r3.get("marubozu_pending")
        if mp:
            key = f"{tf_name}_{mp['candle_time']}_s3maru"
            if key not in maru_pending:
                maru_pending[key] = mp
        if r3.get("signal") in ("BUY", "SELL") and sim_s3_backtest._confirm_ok(
            full_rates, r3.get("signal"), tf_name, tf_secs, int(bar["time"]), fallback_start
        ):
            signals.append((3, r3))
    if 4 in strategies:
        r4 = _call_with_hhll(tf_name, hist_data, strategy_4, scan_rates, tf=tf_name if hist_data else "")
        if r4.get("signal") in ("BUY", "SELL"):
            signals.append((4, r4))
    if 5 in strategies:
        r5 = _call_with_hhll(tf_name, hist_data, strategy_5, scan_rates, tf=tf_name if hist_data else "", signal_time=bt)
        if r5.get("signal") in ("BUY", "SELL"):
            signals.append((5, r5))
    if 8 in strategies:
        r8 = _call_with_hhll(tf_name, hist_data, strategy_8, scan_rates, tf=tf_name if hist_data else "")
        if r8.get("signal") == "MULTI":
            for order in r8.get("orders", []) or []:
                if order.get("signal") in ("BUY", "SELL"):
                    signals.append((8, order))
    return signals


def backtest_tf(tf_name: str, tf_val: int, strategies: set[int], range_end_utc: datetime | None = None) -> list[dict]:
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
    strategy_window = max(
        80,
        int(getattr(config, "TF_LOOKBACK", {}).get(tf_name, getattr(config, "SWING_LOOKBACK", 20)) or 20) + 6,
    )

    trades: list[dict] = []
    pending: list[dict] = []
    open_trades: list[dict] = []
    fired: set[tuple] = set()
    sl_guard = SimSLGuard(point)
    trail_focus_state: dict = {}
    fallback_start: dict = {}
    maru_pending: dict = {}
    tf_secs = TF_SECONDS.get(tf_name, 60)

    for i in range(start_idx, len(bars)):
        bar = bars[i]
        bt = to_bkk(bar["time"])
        h = float(bar["high"])
        l = float(bar["low"])
        full_rates = bars[:i + 1]
        hist_data = _build_historical_hhll_data(full_rates)
        scan_rates = bars[max(0, i - strategy_window + 1):i + 1]
        s8_scan = (
            _call_with_hhll(tf_name, hist_data, strategy_8, scan_rates, tf=tf_name if hist_data else "")
            if 8 in strategies else {"signal": "WAIT"}
        )

        still_pending = []
        for order in pending:
            sid = int(order.get("sid", 0) or 0)
            age_bars = (int(bar["time"]) - int(order.get("detect_time_raw", bar["time"]))) // max(1, int(tf_secs))
            cancel_bars = int(order.get("cancel_bars", 0) or 0)
            cancel_expired = (
                cancel_bars
                and ((sid == 1 and age_bars > cancel_bars) or (sid != 1 and age_bars >= cancel_bars))
            )
            if cancel_expired:
                trades.append({
                    **order,
                    "entry_time": order["detect_time"],
                    "entry_time_raw": order["detect_time_raw"],
                    "close_time": bt,
                    "close_price": None,
                    "close_type": "CANCEL",
                    "pnl": 0.0,
                    "profit": 0.0,
                    "reason": "cancel_bars",
                })
                continue
            if sid == 8 and sim_s8_backtest._cancelled_by_swing_change(order, s8_scan):
                trades.append({
                    **order,
                    "entry_time": order["detect_time"],
                    "entry_time_raw": order["detect_time_raw"],
                    "close_time": bt,
                    "close_price": None,
                    "close_type": "CANCEL",
                    "pnl": 0.0,
                    "profit": 0.0,
                    "reason": "S8 swing changed",
                    "cancel_reason": "S8 swing changed",
                })
                continue
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
            if sid == 8:
                sim_s8_backtest._arm_pending_if_ready(order, bar)

            filled = (
                (order["signal"] == "BUY" and l <= float(order["entry"]))
                or (order["signal"] == "SELL" and h >= float(order["entry"]))
            )
            if not filled:
                still_pending.append(order)
                continue

            trade = _fill_trade(order, bar)
            pd = fill_pdfiboplus_round1(trade, full_rates)
            if pd.get("status") == "fail":
                trades.append(_close_row(trade, "PD_FILL_FAIL", float(bar["close"]), bt))
                continue
            rsi = fill_rsi_recheck(trade, full_rates)
            if rsi.get("status") == "fail":
                trades.append(_close_row(trade, "RSI_FAIL", float(bar["close"]), bt))
                continue
            tr = fill_trend_recheck_round1(trade, full_rates)
            if tr.get("status") == "fail":
                trades.append(_close_row(trade, "TREND_FAIL", float(bar["close"]), bt))
                continue
            open_trades.append(trade)
        pending = still_pending

        opposite_closes = opposite_order_apply(open_trades, pending, bar, spread)
        opposite_close_ids = {id(trade) for trade, _ in opposite_closes}
        guard_activated_sides = []
        still_open = []
        for trade in open_trades:
            sid = int(trade.get("sid", 0) or 0)
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
            sl_active = bool(trade.get("sl_armed", True)) if sid == 8 else True
            if trade["signal"] == "BUY":
                if sl_active and l <= float(trade["sl"]):
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
                if sl_active and h >= float(trade["sl"]):
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
            if not _duplicate_pending(pending, retry_order):
                pending.append(retry_order)

        for sid, result in _scan_signals(
            strategies, scan_rates, full_rates, hist_data, tf_name, bt, bar, tf_secs, fallback_start, maru_pending
        ):
            order = _pending_from_result(result, tf_name, bar, sid)
            if _entry_already_passed(order, bar):
                continue
            key = (
                int(bar["time"]),
                sid,
                order.get("signal"),
                round(float(order.get("entry", 0.0) or 0.0), 2),
                round(float(order.get("sl", 0.0) or 0.0), 2),
                round(float(order.get("tp", 0.0) or 0.0), 2),
                str(order.get("pattern", "")),
            )
            if key in fired:
                continue
            fired.add(key)
            if _duplicate_pending(pending, order):
                continue
            if sl_guard.is_blocked(tf_name, order["signal"], full_rates):
                sl_guard.record_blocked_order(tf_name, order, int(bar["time"]))
                trades.append(trend_cancel_event(order, order["detect_time"], "SL Guard blocked new LIMIT"))
                continue
            if sid == 4:
                pd = sim_s4_backtest._pd_precreate_check(order, scan_rates, tf_name)
            else:
                pd = pending_pdfiboplus_round1(order, full_rates)
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
