from __future__ import annotations

from datetime import datetime, timezone, timedelta

import MetaTrader5 as mt5

import config
from mt5_utils import TF_SECONDS_MAP
from strategy1 import strategy_1


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


def s1_runtime_feature_coverage() -> list[dict]:
    return [
        {
            "name": "S1 pattern detect",
            "config_on": bool(config.active_strategies.get(1, False)),
            "runtime": "apply",
            "replay": "apply",
            "note": "Replay calls shared strategy1.strategy_1()",
        },
        {
            "name": "S1 pending limit lifecycle",
            "config_on": True,
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay models pending limit fill, cancel_bars, and fixed SL/TP",
        },
        {
            "name": "S1 zone mode",
            "config_on": getattr(config, "S1_ZONE_MODE", "zone") == "zone",
            "runtime": "apply",
            "replay": "partial",
            "note": "Initial zone filter is inside strategy_1(); post-create zone cancel/loss-exit is not replayed yet",
        },
        {
            "name": "S1 forward confirm",
            "config_on": True,
            "runtime": "apply",
            "replay": "gap",
            "note": "Runtime cancels/closes if no S2/S3 same-side confirm within 5 bars",
        },
        {
            "name": "PD Fibo Plus",
            "config_on": getattr(config, "PDFIBOPLUS_ENABLED", False),
            "runtime": "apply",
            "replay": "gap",
            "note": "Runtime applies PD Fibo Plus to S1 pending/fill; replay baseline does not yet",
        },
        {
            "name": "Trend/RSI recheck",
            "config_on": getattr(config, "LIMIT_TREND_RECHECK", False) or getattr(config, "PENDING_RSI_RECHECK_ENABLED", False),
            "runtime": "apply",
            "replay": "gap",
            "note": "Runtime can apply trend recheck and RSI fill recheck to S1",
        },
        {
            "name": "Trail/Opposite/Limit Guard",
            "config_on": getattr(config, "TRAIL_SL_ENABLED", False) or getattr(config, "OPPOSITE_ORDER_ENABLED", False) or getattr(config, "LIMIT_GUARD", False),
            "runtime": "apply",
            "replay": "gap",
            "note": "Shared lifecycle features are not included in S1 baseline yet",
        },
    ]


def s1_unreplayed_active_features() -> list[dict]:
    return [
        item for item in s1_runtime_feature_coverage()
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


def _pending_from_result(result: dict, tf_name: str, detect_bar: dict) -> dict:
    return {
        "sid": 1,
        "tf": tf_name,
        "signal": result["signal"],
        "side": result["signal"],
        "pattern": result.get("pattern", "S1"),
        "entry": round(float(result["entry"]), 2),
        "sl": round(float(result["sl"]), 2),
        "tp": round(float(result["tp"]), 2),
        "detect_time": to_bkk(detect_bar["time"]),
        "detect_time_raw": int(detect_bar["time"]),
        "cancel_bars": int(result.get("cancel_bars", 0) or 0),
        "s1_zone_meta": result.get("s1_zone_meta") or {},
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
    start_idx = max(60, next((i for i, r in enumerate(bars) if int(r["time"]) >= since_ts), 60))

    trades: list[dict] = []
    pending: list[dict] = []
    open_trades: list[dict] = []
    fired: set[tuple] = set()

    for i in range(start_idx, len(bars)):
        bar = bars[i]
        bt = to_bkk(bar["time"])
        h = float(bar["high"])
        l = float(bar["low"])

        still_pending = []
        for order in pending:
            age_bars = (int(bar["time"]) - int(order["detect_time_raw"])) // max(1, int(TF_SECONDS_MAP.get(tf_name, 60)))
            cancel_bars = int(order.get("cancel_bars", 0) or 0)
            if cancel_bars and age_bars > cancel_bars:
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

        result = strategy_1(bars[:i + 1], tf=tf_name)
        if result.get("signal") not in ("BUY", "SELL"):
            continue
        key = (
            int(bar["time"]),
            result.get("signal"),
            round(float(result.get("entry", 0.0) or 0.0), 2),
            round(float(result.get("sl", 0.0) or 0.0), 2),
            str(result.get("pattern", "")),
        )
        if key in fired:
            continue
        fired.add(key)
        pending.append(_pending_from_result(result, tf_name, bar))

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
