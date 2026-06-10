from __future__ import annotations

from datetime import datetime, timezone, timedelta

import MetaTrader5 as mt5

import config
from strategy8 import strategy_8


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


def s8_runtime_feature_coverage() -> list[dict]:
    return [
        {
            "name": "S8 swing-limit detect",
            "config_on": bool(config.active_strategies.get(8, False)),
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay calls strategy8.strategy_8() with historical bar-scan fallback instead of live HHLL cache",
        },
        {
            "name": "Dual-side pending placement",
            "config_on": True,
            "runtime": "apply",
            "replay": "apply",
            "note": "Replay can place both BUY and SELL S8 limits from one scan result",
        },
        {
            "name": "Delayed SL arm",
            "config_on": True,
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay models default S8 breakout arm and fill fallback; time/price delay modes are approximated",
        },
        {
            "name": "S8 swing-change cancel",
            "config_on": True,
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay cancels pending when the same-side reference swing no longer matches the latest historical scan",
        },
        {
            "name": "Limit Sweep follow-up S8",
            "config_on": getattr(config, "LIMIT_SWEEP", False),
            "runtime": "apply",
            "replay": "gap",
            "note": "Runtime can create S8 orders after sweep management; baseline only scans native S8",
        },
        {
            "name": "PD Fibo Plus",
            "config_on": getattr(config, "PDFIBOPLUS_ENABLED", False),
            "runtime": "apply",
            "replay": "gap",
            "note": "Runtime applies PD Fibo Plus to S8 pending/fill",
        },
        {
            "name": "Limit Trend/Fill Trend Recheck",
            "config_on": getattr(config, "LIMIT_TREND_RECHECK", False),
            "runtime": "apply",
            "replay": "gap",
            "note": "Runtime applies trend recheck to S8 pending/fill",
        },
        {
            "name": "Trail/Opposite/Limit Guard",
            "config_on": getattr(config, "TRAIL_SL_ENABLED", False) or getattr(config, "OPPOSITE_ORDER_ENABLED", False) or getattr(config, "LIMIT_GUARD", False),
            "runtime": "apply",
            "replay": "gap",
            "note": "Shared lifecycle features are not included in S8 baseline yet",
        },
    ]


def s8_unreplayed_active_features() -> list[dict]:
    return [
        item for item in s8_runtime_feature_coverage()
        if item["config_on"] and item["replay"] == "gap"
    ]


def _as_records(rates) -> list[dict]:
    return sorted(
        [{name: r[name] for name in rates.dtype.names} for r in rates],
        key=lambda r: int(r["time"]),
    )


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
        "sid": 8,
        "tf": tf_name,
        "signal": signal,
        "side": signal,
        "pattern": result.get("pattern", "S8 Swing Limit"),
        "entry": round(float(result["entry"]), 2),
        "sl": round(float(result["sl"]), 2),
        "tp": round(float(result["tp"]), 2),
        "intended_sl": round(float(result["sl"]), 2),
        "sl_armed": False,
        "swing_price": float(result.get("swing_price", 0.0) or 0.0),
        "swing_bar_time": int(result.get("swing_bar_time", 0) or 0),
        "detect_time": to_bkk(detect_bar["time"]),
        "detect_time_raw": int(detect_bar["time"]),
    }


def _arm_pending_if_ready(order: dict, bar: dict) -> None:
    if order.get("sl_armed"):
        return
    mode = getattr(config, "DELAY_SL_MODE", "off")
    if mode != "off":
        order["sl_armed"] = True
        return

    swing_price = float(order.get("swing_price", 0.0) or 0.0)
    swing_bar_time = int(order.get("swing_bar_time", 0) or 0)
    if swing_price <= 0 or int(bar["time"]) <= swing_bar_time:
        return
    if order["signal"] == "SELL" and float(bar["high"]) > swing_price:
        order["sl_armed"] = True
    elif order["signal"] == "BUY" and float(bar["low"]) < swing_price:
        order["sl_armed"] = True


def _fill_trade(order: dict, bar: dict) -> dict:
    sl_armed = bool(order.get("sl_armed"))
    if not sl_armed and getattr(config, "DELAY_SL_MODE", "off") == "off":
        sl_armed = True
    return {
        **order,
        "sl_armed": sl_armed,
        "entry_time": to_bkk(bar["time"]),
        "entry_time_raw": int(bar["time"]),
        "close_type": "OPEN",
    }


def _same_side_scan_order(scan_result: dict, signal: str) -> dict | None:
    if scan_result.get("signal") != "MULTI":
        return None
    for order in scan_result.get("orders", []) or []:
        if order.get("signal") == signal:
            return order
    return None


def _cancelled_by_swing_change(order: dict, scan_result: dict) -> bool:
    latest = _same_side_scan_order(scan_result, order["signal"])
    if not latest:
        return True
    old_swing = float(order.get("swing_price", 0.0) or 0.0)
    new_swing = float(latest.get("swing_price", 0.0) or 0.0)
    if old_swing <= 0 or new_swing <= 0:
        return False
    return abs(old_swing - new_swing) > 0.01


def backtest_tf(tf_name: str, tf_val: int) -> list[dict]:
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, TF_EXTRA_BARS.get(tf_name, 500) + 8000)
    if rates is None or len(rates) < 120:
        return []
    bars = _as_records(rates)
    since_ts = int(SINCE.timestamp())
    start_idx = max(80, next((i for i, r in enumerate(bars) if int(r["time"]) >= since_ts), 80))
    strategy_window = max(80, int(getattr(config, "TF_LOOKBACK", {}).get(tf_name, getattr(config, "SWING_LOOKBACK", 20)) or 20) + 6)

    trades: list[dict] = []
    pending: list[dict] = []
    open_trades: list[dict] = []
    fired: set[tuple] = set()

    for i in range(start_idx, len(bars)):
        bar = bars[i]
        bt = to_bkk(bar["time"])
        h = float(bar["high"])
        l = float(bar["low"])

        scan_rates = bars[max(0, i - strategy_window + 1):i + 1]
        scan_result = strategy_8(scan_rates, tf="")

        still_pending = []
        for order in pending:
            if _cancelled_by_swing_change(order, scan_result):
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
            _arm_pending_if_ready(order, bar)
            if order["signal"] == "BUY" and l <= float(order["entry"]):
                open_trades.append(_fill_trade(order, bar))
            elif order["signal"] == "SELL" and h >= float(order["entry"]):
                open_trades.append(_fill_trade(order, bar))
            else:
                still_pending.append(order)
        pending = still_pending

        still_open = []
        for trade in open_trades:
            sl_active = bool(trade.get("sl_armed", True))
            if trade["signal"] == "BUY":
                if sl_active and l <= float(trade["sl"]):
                    trades.append(_close_row(trade, "SL", trade["sl"], bt))
                    continue
                if h >= float(trade["tp"]):
                    trades.append(_close_row(trade, "TP", trade["tp"], bt))
                    continue
            else:
                if sl_active and h >= float(trade["sl"]):
                    trades.append(_close_row(trade, "SL", trade["sl"], bt))
                    continue
                if l <= float(trade["tp"]):
                    trades.append(_close_row(trade, "TP", trade["tp"], bt))
                    continue
            still_open.append(trade)
        open_trades = still_open

        result = scan_result
        if result.get("signal") != "MULTI":
            continue
        for order_result in result.get("orders", []):
            if order_result.get("signal") not in ("BUY", "SELL"):
                continue
            if _entry_already_passed(order_result, bar):
                continue
            key = (
                int(bar["time"]),
                order_result.get("signal"),
                round(float(order_result.get("entry", 0.0) or 0.0), 2),
                round(float(order_result.get("sl", 0.0) or 0.0), 2),
                round(float(order_result.get("tp", 0.0) or 0.0), 2),
                str(order_result.get("pattern", "")),
            )
            if key in fired:
                continue
            duplicate_pending = any(
                p["signal"] == order_result.get("signal")
                and abs(float(p["entry"]) - float(order_result.get("entry", 0.0) or 0.0)) <= 0.01
                and abs(float(p["sl"]) - float(order_result.get("sl", 0.0) or 0.0)) <= 0.01
                and abs(float(p["tp"]) - float(order_result.get("tp", 0.0) or 0.0)) <= 0.01
                for p in pending
            )
            if duplicate_pending:
                continue
            fired.add(key)
            pending.append(_pending_from_result(order_result, tf_name, bar))

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
