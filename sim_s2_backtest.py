from __future__ import annotations

from datetime import datetime, timezone, timedelta

import MetaTrader5 as mt5

import config
from mt5_utils import TF_SECONDS_MAP, find_swing_tp
from scanner import _find_recent_signal_confirmation, _has_swing_in_lookback
from strategy2 import strategy_2


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


def s2_runtime_feature_coverage() -> list[dict]:
    return [
        {
            "name": "S2 FVG detect",
            "config_on": bool(config.active_strategies.get(2, False)),
            "runtime": "apply",
            "replay": "apply",
            "note": "Replay calls shared strategy2.strategy_2()",
        },
        {
            "name": "S2 normal confirm lookback",
            "config_on": bool(getattr(config, "FVG_NORMAL", False)),
            "runtime": "apply",
            "replay": "apply",
            "note": "Replay uses scanner confirmation helper plus swing fallback",
        },
        {
            "name": "S2 FVG parallel intersection",
            "config_on": bool(getattr(config, "FVG_PARALLEL", False)),
            "runtime": "apply",
            "replay": "gap",
            "note": "Runtime intersects pending orders across TFs; baseline replay is single-TF normal path",
        },
        {
            "name": "Pending limit lifecycle",
            "config_on": True,
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay models pending fill, cancel_bars, and fixed SL/TP with bar high/low",
        },
        {
            "name": "PD Fibo Plus",
            "config_on": getattr(config, "PDFIBOPLUS_ENABLED", False),
            "runtime": "apply",
            "replay": "gap",
            "note": "Runtime has S2 gap-aware PD pass and can adjust entry to EQ/50%",
        },
        {
            "name": "Limit Trend/Fill Trend Recheck",
            "config_on": getattr(config, "LIMIT_TREND_RECHECK", False),
            "runtime": "apply",
            "replay": "gap",
            "note": "Runtime applies trend recheck to S2 pending/fill",
        },
        {
            "name": "RSI Fill Recheck",
            "config_on": getattr(config, "PENDING_RSI_RECHECK_ENABLED", False),
            "runtime": "apply",
            "replay": "gap",
            "note": "Runtime can close S2 after fill when RSI recheck fails",
        },
        {
            "name": "Limit TP/SL Break Cancel",
            "config_on": getattr(config, "LIMIT_BREAK_CANCEL", False),
            "runtime": "apply",
            "replay": "gap",
            "note": "Runtime skips engulf pattern 1 but can cancel other S2 patterns",
        },
        {
            "name": "Trail/Opposite/Limit Guard",
            "config_on": getattr(config, "TRAIL_SL_ENABLED", False) or getattr(config, "OPPOSITE_ORDER_ENABLED", False) or getattr(config, "LIMIT_GUARD", False),
            "runtime": "apply",
            "replay": "gap",
            "note": "Shared lifecycle features are not included in S2 baseline yet",
        },
    ]


def s2_unreplayed_active_features() -> list[dict]:
    return [
        item for item in s2_runtime_feature_coverage()
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


def _calc_tp(rates: list[dict], signal: str, entry: float, sl: float, tf_name: str) -> float:
    tp_swing = find_swing_tp(rates, signal, entry, sl, tf=tf_name)
    if tp_swing:
        return round(float(tp_swing), 2)
    if signal == "BUY":
        return round(float(entry) + abs(float(entry) - float(sl)), 2)
    return round(float(entry) - abs(float(sl) - float(entry)), 2)


def _pending_from_fvg(fvg: dict, tf_name: str, detect_bar: dict, tp: float) -> dict:
    return {
        "sid": 2,
        "tf": tf_name,
        "signal": fvg["signal"],
        "side": fvg["signal"],
        "pattern": fvg.get("pattern", "S2 FVG"),
        "entry": round(float(fvg["entry"]), 2),
        "sl": round(float(fvg["sl"]), 2),
        "tp": round(float(tp), 2),
        "detect_time": to_bkk(detect_bar["time"]),
        "detect_time_raw": int(detect_bar["time"]),
        "gap_bot": round(float(fvg.get("gap_bot", 0.0) or 0.0), 2),
        "gap_top": round(float(fvg.get("gap_top", 0.0) or 0.0), 2),
        "final_gap_bot": round(float(fvg.get("gap_bot", 0.0) or 0.0), 2),
        "final_gap_top": round(float(fvg.get("gap_top", 0.0) or 0.0), 2),
        "c3_type": fvg.get("c3_type", ""),
        "cancel_bars": 1 if fvg.get("c3_type") == "ปฏิเสธราคา" else 0,
    }


def _fill_trade(order: dict, bar: dict) -> dict:
    return {
        **order,
        "entry_time": to_bkk(bar["time"]),
        "entry_time_raw": int(bar["time"]),
        "close_type": "OPEN",
    }


def _s2_confirm_ok(rates: list[dict], signal: str, tf_name: str, tf_secs: int, last_candle_time: int, fallback_start: dict) -> bool:
    if not getattr(config, "FVG_NORMAL", False):
        return False
    confirm = _find_recent_signal_confirmation(
        rates,
        signal,
        tf_secs,
        getattr(config, "S2_NORMAL_CONFIRM_LOOKBACK_BARS", 8),
    )
    if confirm:
        return True

    key = (tf_name, signal)
    if key not in fallback_start:
        fallback_start[key] = last_candle_time
    bars_waited = (last_candle_time - fallback_start[key]) // max(1, tf_secs)
    if bars_waited >= 4 and _has_swing_in_lookback(rates, signal, 8):
        fallback_start.pop(key, None)
        return True
    return False


def backtest_tf(tf_name: str, tf_val: int) -> list[dict]:
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, TF_EXTRA_BARS.get(tf_name, 500) + 8000)
    if rates is None or len(rates) < 120:
        return []
    bars = _as_records(rates)
    since_ts = int(SINCE.timestamp())
    start_idx = max(80, next((i for i, r in enumerate(bars) if int(r["time"]) >= since_ts), 80))
    tf_secs = int(TF_SECONDS_MAP.get(tf_name, 60))

    trades: list[dict] = []
    pending: list[dict] = []
    open_trades: list[dict] = []
    fired: set[tuple] = set()
    fallback_start: dict = {}

    for i in range(start_idx, len(bars)):
        bar = bars[i]
        bt = to_bkk(bar["time"])
        h = float(bar["high"])
        l = float(bar["low"])

        still_pending = []
        for order in pending:
            age_bars = (int(bar["time"]) - int(order["detect_time_raw"])) // max(1, tf_secs)
            cancel_bars = int(order.get("cancel_bars", 0) or 0)
            if cancel_bars and age_bars >= cancel_bars:
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

        result = strategy_2(bars[:i + 1], tf=tf_name)
        if result.get("signal") != "FVG_DETECTED":
            continue
        fvg = result.get("fvg") or {}
        signal = fvg.get("signal")
        if signal not in ("BUY", "SELL"):
            continue
        if not _s2_confirm_ok(bars[:i + 1], signal, tf_name, tf_secs, int(bar["time"]), fallback_start):
            continue

        tp = _calc_tp(bars[:i + 1], signal, float(fvg["entry"]), float(fvg["sl"]), tf_name)
        key = (
            int(bar["time"]),
            signal,
            round(float(fvg.get("entry", 0.0) or 0.0), 2),
            round(float(fvg.get("sl", 0.0) or 0.0), 2),
            round(float(tp), 2),
            str(fvg.get("c3_type", "")),
        )
        if key in fired:
            continue
        fired.add(key)
        pending.append(_pending_from_fvg(fvg, tf_name, bar, tp))

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
