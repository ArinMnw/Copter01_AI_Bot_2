from __future__ import annotations

from datetime import datetime, timezone, timedelta

import MetaTrader5 as mt5

import config
from sim_lifecycle import fill_pdfiboplus_round1, pd_cancel_event, pending_pdfiboplus_round1
import strategy11
from strategy1 import strategy_1
from strategy11 import record_s1_pattern, reset_state, strategy_11


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
    "M1": 2500,
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


def _pd_enabled_for_s11() -> bool:
    return 11 not in set(getattr(config, "PDFIBOPLUS_SKIP_SIDS", ()))


def s11_runtime_feature_coverage() -> list[dict]:
    pd_enabled = _pd_enabled_for_s11()
    return [
        {
            "name": "S1 anchor hook",
            "config_on": bool(config.active_strategies.get(11, False)),
            "runtime": "apply",
            "replay": "apply",
            "note": "Replay calls strategy1.strategy_1() and strategy11.record_s1_pattern()",
        },
        {
            "name": "S11 Fibo state/cascade",
            "config_on": bool(config.active_strategies.get(11, False)),
            "runtime": "apply",
            "replay": "apply",
            "note": "Replay calls shared strategy11.strategy_11()",
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
            "runtime": "apply" if pd_enabled else "skip_s11",
            "replay": "partial" if pd_enabled else "skip_s11",
            "note": (
                "Replay applies pending and fill round1 gates; round2 is not included yet"
                if pd_enabled
                else "Runtime skips S11 via config.PDFIBOPLUS_SKIP_SIDS"
            ),
        },
        {
            "name": "Limit Trend / RSI Recheck",
            "config_on": getattr(config, "LIMIT_TREND_RECHECK", False) or getattr(config, "PENDING_RSI_RECHECK_ENABLED", False),
            "runtime": "skip_s11",
            "replay": "skip_s11",
            "note": "Runtime skips S11 in pending trend and RSI fill recheck",
        },
        {
            "name": "Strong Trend Block",
            "config_on": getattr(config, "STRONG_TREND_BLOCK_ENABLED", False),
            "runtime": "apply",
            "replay": "gap",
            "note": "Runtime can scan-block S11 when strong trend block is enabled",
        },
        {
            "name": "Duplicate/adjacent guards",
            "config_on": True,
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay blocks same pending setup and adjacent same-SID bar while S11 exposure is active",
        },
        {
            "name": "S1 linked cleanup",
            "config_on": True,
            "runtime": "apply",
            "replay": "gap",
            "note": "Runtime can cancel/close linked S11 when S1 forward lifecycle invalidates",
        },
        {
            "name": "SL Guard",
            "config_on": bool(getattr(config, "SL_GUARD_GROUP_ENABLED", False)),
            "runtime": "apply",
            "replay": "partial",
            "note": "Central runner can apply SL Guard Group close-on-activate overlay with context TFs",
        },
        {
            "name": "Trail/Opposite/Limit Guard",
            "config_on": getattr(config, "TRAIL_SL_ENABLED", False) or getattr(config, "OPPOSITE_ORDER_ENABLED", False) or getattr(config, "LIMIT_GUARD", False),
            "runtime": "apply",
            "replay": "gap",
            "note": "Trail SL, Opposite Order, and Limit Guard are not included in S11 baseline yet",
        },
    ]


def s11_unreplayed_active_features() -> list[dict]:
    return [
        item for item in s11_runtime_feature_coverage()
        if item["config_on"] and item["replay"] == "gap"
    ]


def _as_records(rates) -> list[dict]:
    return sorted(
        [{name: r[name] for name in rates.dtype.names} for r in rates],
        key=lambda r: int(r["time"]),
    )


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


def _same_price(a, b, tol: float = 0.05) -> bool:
    try:
        return abs(float(a) - float(b)) <= float(tol)
    except Exception:
        return False


def _has_duplicate_pending(pending: list[dict], order: dict, tol: float = 0.05) -> bool:
    for existing in pending:
        if existing.get("tf") != order.get("tf"):
            continue
        if int(existing.get("sid", 0) or 0) != int(order.get("sid", 0) or 0):
            continue
        if existing.get("signal") != order.get("signal"):
            continue
        if not _same_price(existing.get("entry"), order.get("entry"), tol):
            continue
        if not _same_price(existing.get("sl"), order.get("sl"), tol):
            continue
        if not _same_price(existing.get("tp"), order.get("tp"), tol):
            continue
        return True
    return False


def _has_active_s11_trade(pending: list[dict], open_trades: list[dict], tf_name: str) -> bool:
    return any(t.get("tf") == tf_name for t in pending) or any(t.get("tf") == tf_name for t in open_trades)


def _pending_from_result(result: dict, tf_name: str, detect_bar: dict) -> dict:
    signal = result["signal"]
    return {
        "sid": 11,
        "tf": tf_name,
        "signal": signal,
        "side": signal,
        "pattern": result.get("pattern", "S11 Fibo S1"),
        "entry": round(float(result["entry"]), 2),
        "sl": round(float(result["sl"]), 2),
        "tp": round(float(result["tp"]), 2),
        "detect_time": to_bkk(detect_bar["time"]),
        "detect_time_raw": int(detect_bar["time"]),
        "order_mode": result.get("order_mode", "limit"),
    }


def _fill_trade(order: dict, bar: dict) -> dict:
    return {
        **order,
        "entry_time": to_bkk(bar["time"]),
        "entry_time_raw": int(bar["time"]),
        "close_type": "OPEN",
    }


def backtest_tf(tf_name: str, tf_val: int) -> list[dict]:
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, TF_EXTRA_BARS.get(tf_name, 500) + 8000)
    if rates is None or len(rates) < 120:
        return []
    bars = _as_records(rates)
    since_ts = int(SINCE.timestamp())
    start_idx = max(80, next((i for i, r in enumerate(bars) if int(r["time"]) >= since_ts), 80))
    strategy_window = max(40, int(getattr(config, "TF_LOOKBACK", {}).get(tf_name, getattr(config, "SWING_LOOKBACK", 20)) or 20) + 6)

    reset_state(tf_name)
    trades: list[dict] = []
    pending: list[dict] = []
    open_trades: list[dict] = []
    fired: set[tuple] = set()
    last_traded_sid_time: int | None = None
    tf_secs = int(TF_SECONDS.get(tf_name, 0) or 0)

    for i in range(start_idx, len(bars)):
        bar = bars[i]
        bt = to_bkk(bar["time"])
        h = float(bar["high"])
        l = float(bar["low"])

        still_pending = []
        for order in pending:
            if order["signal"] == "BUY" and l <= float(order["entry"]):
                trade = _fill_trade(order, bar)
                pd = fill_pdfiboplus_round1(trade, bars[:i + 1]) if _pd_enabled_for_s11() else {"status": "skip"}
                if pd.get("status") == "fail":
                    trades.append(_close_row(trade, "PD_FAIL", float(bar["close"]), bt))
                else:
                    open_trades.append(trade)
            elif order["signal"] == "SELL" and h >= float(order["entry"]):
                trade = _fill_trade(order, bar)
                pd = fill_pdfiboplus_round1(trade, bars[:i + 1]) if _pd_enabled_for_s11() else {"status": "skip"}
                if pd.get("status") == "fail":
                    trades.append(_close_row(trade, "PD_FAIL", float(bar["close"]), bt))
                else:
                    open_trades.append(trade)
            else:
                still_pending.append(order)
        pending = still_pending

        still_open = []
        for trade in open_trades:
            if trade["signal"] == "BUY":
                if l <= float(trade["sl"]):
                    trades.append(_close_row(trade, "SL", trade["sl"], bt))
                    continue
                if h >= float(trade["tp"]):
                    trades.append(_close_row(trade, "TP", trade["tp"], bt))
                    continue
            else:
                if h >= float(trade["sl"]):
                    trades.append(_close_row(trade, "SL", trade["sl"], bt))
                    continue
                if l <= float(trade["tp"]):
                    trades.append(_close_row(trade, "TP", trade["tp"], bt))
                    continue
            still_open.append(trade)
        open_trades = still_open

        scan_rates = bars[max(0, i - strategy_window + 1):i + 1]
        s1 = strategy_1(scan_rates, tf=tf_name)
        if s1.get("signal") in ("BUY", "SELL"):
            record_s1_pattern(
                tf_name,
                s1.get("signal"),
                s1.get("candles") or [],
                int(bar["time"]),
                s1.get("pattern", ""),
            )

        result = strategy_11(scan_rates, tf_name)
        if result.get("signal") not in ("BUY", "SELL"):
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
        if _has_duplicate_pending(pending, order):
            continue
        if (
            last_traded_sid_time
            and tf_secs > 0
            and int(bar["time"]) - int(last_traded_sid_time) == tf_secs
            and _has_active_s11_trade(pending, open_trades, tf_name)
        ):
            continue
        if _pd_enabled_for_s11():
            pd = pending_pdfiboplus_round1(order, bars[:i + 1])
            if pd.get("status") == "fail":
                trades.append(pd_cancel_event(order, order["detect_time"]))
                continue
        pending.append(order)
        last_traded_sid_time = int(bar["time"])

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
    strategy11.reset_state(tf_name)
    return trades
