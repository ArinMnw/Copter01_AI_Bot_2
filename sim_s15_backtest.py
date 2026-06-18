from __future__ import annotations

from datetime import datetime, timezone, timedelta

import MetaTrader5 as mt5

import config
import strategy15
from strategy15 import strategy_15


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


def s15_runtime_feature_coverage() -> list[dict]:
    return [
        {
            "name": "S15 VP absorption detect",
            "config_on": bool(config.active_strategies.get(15, False)),
            "runtime": "apply",
            "replay": "apply",
            "note": "Replay calls shared strategy15.strategy_15() with replay-safe cooldown",
        },
        {
            "name": "S15 limit lifecycle",
            "config_on": True,
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay models pending limit fill then fixed SL/TP; broker tick ordering can drift",
        },
        {
            "name": "PD Fibo Plus",
            "config_on": getattr(config, "PDFIBOPLUS_ENABLED", False),
            "runtime": "skip_s15",
            "replay": "skip_s15",
            "note": "Runtime skips SIDs 9,10,13,14,15,16",
        },
        {
            "name": "Trend Recheck",
            "config_on": getattr(config, "LIMIT_TREND_RECHECK", False),
            "runtime": "skip_s15",
            "replay": "skip_s15",
            "note": "Runtime skips S15 trend recheck",
        },
        {
            "name": "RSI Fill Recheck",
            "config_on": getattr(config, "PENDING_RSI_RECHECK_ENABLED", False),
            "runtime": "skip_s15",
            "replay": "skip_s15",
            "note": "Runtime skips S15 RSI fill recheck",
        },
        {
            "name": "Trail SL",
            "config_on": getattr(config, "TRAIL_SL_ENABLED", False),
            "runtime": "skip_s15",
            "replay": "skip_s15",
            "note": "Runtime Trail SL skips S15",
        },
        {
            "name": "Opposite Order",
            "config_on": getattr(config, "OPPOSITE_ORDER_ENABLED", False),
            "runtime": "skip_s15",
            "replay": "skip_s15",
            "note": "Runtime opposite-order handling filters S15",
        },
        {
            "name": "Limit Guard",
            "config_on": getattr(config, "LIMIT_GUARD", False),
            "runtime": "skip_s15",
            "replay": "skip_s15",
            "note": "Runtime skips S15 limit guard because VP levels can be intentionally far",
        },
        {
            "name": "SL Guard",
            "config_on": getattr(config, "SL_GUARD_ENABLED", False) or getattr(config, "SL_GUARD_GROUP_ENABLED", False),
            "runtime": "apply",
            "replay": "partial",
            "note": "S15 keeps SL Guard; central replay applies SL Guard Group close-on-activate overlay as a baseline",
        },
    ]


def s15_unreplayed_active_features() -> list[dict]:
    return [
        item for item in s15_runtime_feature_coverage()
        if item["config_on"] and item["replay"] == "gap"
    ]


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


def _pending_from_order(order: dict, tf_name: str, detect_bar: dict) -> dict:
    return {
        "sid": 15,
        "tf": tf_name,
        "signal": order["signal"],
        "side": order["signal"],
        "pattern": order.get("pattern", "S15"),
        "entry": round(float(order["entry"]), 2),
        "sl": round(float(order["sl"]), 2),
        "tp": round(float(order["tp"]), 2),
        "detect_time": to_bkk(detect_bar["time"]),
        "detect_time_raw": int(detect_bar["time"]),
        "vp_poc": order.get("vp_poc"),
        "vp_val": order.get("vp_val"),
        "vp_vah": order.get("vp_vah"),
    }


def _fill_trade(pending: dict, bar: dict) -> dict:
    return {
        **pending,
        "entry_time": to_bkk(bar["time"]),
        "entry_time_raw": int(bar["time"]),
        "close_type": "OPEN",
    }


def backtest_tf(tf_name: str, tf_val: int) -> list[dict]:
    extra = TF_EXTRA_BARS.get(tf_name, 500)
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, extra + 7000)
    if rates is None or len(rates) < 120:
        return []
    bars = sorted(
        [{name: r[name] for name in rates.dtype.names} for r in rates],
        key=lambda r: int(r["time"]),
    )
    since_ts = int(SINCE.timestamp())
    lookback = int(getattr(config, "S15_LOOKBACK", 100)) + 10
    start_idx = max(lookback, next((i for i, r in enumerate(bars) if int(r["time"]) >= since_ts), lookback))

    old_global_cd = getattr(config, "S15_GLOBAL_COOLDOWN_SECS", 300)
    strategy15._s15_last_fire.clear()
    strategy15._s15_global_last.update({"BUY": 0.0, "SELL": 0.0})
    config.S15_GLOBAL_COOLDOWN_SECS = 0

    trades: list[dict] = []
    pending: list[dict] = []
    open_trades: list[dict] = []

    try:
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

            result = strategy_15(bars[:i + 1], tf=tf_name)
            sig = result.get("signal", "WAIT")
            orders = result.get("orders", [result]) if sig == "MULTI" else ([result] if sig in ("BUY", "SELL") else [])
            for order in orders:
                if order.get("order_mode") != "limit":
                    continue
                pending.append(_pending_from_order(order, tf_name, bar))
    finally:
        config.S15_GLOBAL_COOLDOWN_SECS = old_global_cd

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
