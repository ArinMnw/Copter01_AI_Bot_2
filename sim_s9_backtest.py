from __future__ import annotations

from datetime import datetime, timezone, timedelta

import MetaTrader5 as mt5

import config
from strategy9 import strategy_9


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


def to_bkk(ts: int) -> datetime:
    return datetime.fromtimestamp(int(ts), tz=UTC) + timedelta(hours=TZ_OFF - SRV_TZ)


def profit(price_diff: float) -> float:
    return round(float(price_diff) * PRICE_TO_USD, 2)


def s9_runtime_feature_coverage() -> list[dict]:
    return [
        {
            "name": "S9 RSI divergence detect",
            "config_on": bool(config.active_strategies.get(9, False)),
            "runtime": "apply",
            "replay": "apply",
            "note": "Replay calls shared strategy9.strategy_9()",
        },
        {
            "name": "S9 setup dedup / passed-entry",
            "config_on": True,
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay dedups pivot setup_sig and invalidates setup when signal-bar close has passed limit entry",
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
            "runtime": "skip_s9",
            "replay": "skip_s9",
            "note": "Runtime skips S9 PD Fibo Plus",
        },
        {
            "name": "Limit Trend / Fill Trend Recheck",
            "config_on": getattr(config, "LIMIT_TREND_RECHECK", False),
            "runtime": "skip_s9",
            "replay": "skip_s9",
            "note": "Runtime skips S9 trend recheck",
        },
        {
            "name": "RSI Fill Recheck",
            "config_on": getattr(config, "PENDING_RSI_RECHECK_ENABLED", False),
            "runtime": "skip_s9",
            "replay": "skip_s9",
            "note": "Runtime skips S9 RSI fill recheck",
        },
        {
            "name": "Strong Trend Block",
            "config_on": getattr(config, "STRONG_TREND_BLOCK_ENABLED", False),
            "runtime": "apply",
            "replay": "gap",
            "note": "Runtime can scan-block S9 when strong trend block is enabled",
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
            "note": "Trail SL, Opposite Order, and Limit Guard are not included in S9 baseline yet",
        },
    ]


def s9_unreplayed_active_features() -> list[dict]:
    return [
        item for item in s9_runtime_feature_coverage()
        if item["config_on"] and item["replay"] == "gap"
    ]


def _as_records(rates) -> list[dict]:
    return sorted(
        [{name: r[name] for name in rates.dtype.names} for r in rates],
        key=lambda r: int(r["time"]),
    )


def _setup_sig(tf_name: str, signal: str, result: dict) -> str:
    div_type = result.get("div_type", "") or ""
    pivot_prev_time = int(result.get("pivot_prev_time", 0) or 0)
    pivot_cur_time = int(result.get("pivot_cur_time", 0) or 0)
    if not (div_type and pivot_prev_time and pivot_cur_time):
        return ""
    return f"{tf_name}|{signal}|{div_type}|{pivot_prev_time}|{pivot_cur_time}"


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


def _pending_from_result(result: dict, tf_name: str, detect_bar: dict, setup_sig: str) -> dict:
    signal = result["signal"]
    return {
        "sid": 9,
        "tf": tf_name,
        "signal": signal,
        "side": signal,
        "pattern": result.get("pattern", "S9 RSI Divergence"),
        "entry": round(float(result["entry"]), 2),
        "sl": round(float(result["sl"]), 2),
        "tp": round(float(result["tp"]), 2),
        "detect_time": to_bkk(detect_bar["time"]),
        "detect_time_raw": int(detect_bar["time"]),
        "setup_sig": setup_sig,
        "div_type": result.get("div_type", ""),
        "pivot_prev_time": result.get("pivot_prev_time"),
        "pivot_cur_time": result.get("pivot_cur_time"),
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
    strategy_window = max(
        80,
        int(getattr(config, "TF_LOOKBACK", {}).get(tf_name, getattr(config, "SWING_LOOKBACK", 20)) or 20) + 6,
        int(getattr(config, "RSI9_PERIOD", 14))
        + int(getattr(config, "RSI9_PIVOT_LOOKBACK_LEFT", 5))
        + int(getattr(config, "RSI9_PIVOT_LOOKBACK_RIGHT", 5))
        + int(getattr(config, "RSI9_LOOKBACK_RANGE_MAX", 60))
        + 10,
    )

    trades: list[dict] = []
    pending: list[dict] = []
    open_trades: list[dict] = []
    seen_setup: set[str] = set()
    invalid_setup: set[str] = set()

    for i in range(start_idx, len(bars)):
        bar = bars[i]
        bt = to_bkk(bar["time"])
        h = float(bar["high"])
        l = float(bar["low"])

        still_pending = []
        for order in pending:
            if order["signal"] == "BUY" and l <= float(order["entry"]):
                open_trades.append(_fill_trade(order, bar))
            elif order["signal"] == "SELL" and h >= float(order["entry"]):
                open_trades.append(_fill_trade(order, bar))
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
        result = strategy_9(scan_rates, tf=tf_name)
        if result.get("signal") not in ("BUY", "SELL"):
            continue
        setup_sig = _setup_sig(tf_name, result["signal"], result)
        if setup_sig and (setup_sig in seen_setup or setup_sig in invalid_setup):
            continue
        if _entry_already_passed(result, bar):
            if setup_sig:
                invalid_setup.add(setup_sig)
            continue
        if setup_sig:
            seen_setup.add(setup_sig)
        pending.append(_pending_from_result(result, tf_name, bar, setup_sig))

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
