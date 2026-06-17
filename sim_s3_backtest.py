from __future__ import annotations

from datetime import datetime, timezone, timedelta

import MetaTrader5 as mt5

import config
from mt5_utils import TF_SECONDS_MAP
from scanner import _find_recent_signal_confirmation, _has_swing_in_lookback
from sim_lifecycle import fill_pdfiboplus_round1, pd_cancel_event, pending_pdfiboplus_round1
from strategy3 import strategy_3


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


def s3_runtime_feature_coverage() -> list[dict]:
    return [
        {
            "name": "S3 DM/SP detect",
            "config_on": bool(config.active_strategies.get(3, False)),
            "runtime": "apply",
            "replay": "apply",
            "note": "Replay uses range-based MT5 fetch and calls shared strategy3.strategy_3()",
        },
        {
            "name": "S3 normal confirm lookback",
            "config_on": True,
            "runtime": "apply",
            "replay": "apply",
            "note": "Replay uses scanner confirmation helper plus swing fallback",
        },
        {
            "name": "S3 Marubozu / No Engulf pending",
            "config_on": True,
            "runtime": "apply",
            "replay": "apply",
            "note": "Replay waits one closed bar and places limit only when color confirms",
        },
        {
            "name": "Adjacent same-sid scan block",
            "config_on": True,
            "runtime": "apply",
            "replay": "partial",
            "note": "Unified S1-S5/S8 path blocks adjacent same-sid orders when an active same-sid trade remains",
        },
        {
            "name": "Sweep Filter scan block",
            "config_on": getattr(config, "SWEEP_FILTER_ENABLED", False),
            "runtime": "apply",
            "replay": "partial",
            "note": "Unified S1-S5/S8 path uses historical sweep detection to block counter-sweep scan signals",
        },
        {
            "name": "Trend Filter scan block",
            "config_on": getattr(config, "TREND_FILTER_SCAN_BLOCK", False),
            "runtime": "apply",
            "replay": "ready",
            "note": "Config is currently OFF in tested state; full breakout-mode scan block is a ready/off layer",
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
            "runtime": "skip_s3",
            "replay": "skip_s3",
            "note": "Runtime skips S3 PD Fibo Plus",
        },
        {
            "name": "Limit Trend/Fill Trend Recheck",
            "config_on": getattr(config, "LIMIT_TREND_RECHECK", False),
            "runtime": "skip_s3",
            "replay": "skip_s3",
            "note": "Runtime skips S3 pending/fill trend recheck",
        },
        {
            "name": "RSI Fill Recheck",
            "config_on": getattr(config, "PENDING_RSI_RECHECK_ENABLED", False),
            "runtime": "apply",
            "replay": "gap",
            "note": "Runtime can close S3 after fill when RSI recheck fails",
        },
        {
            "name": "Trail/Opposite/Limit Guard",
            "config_on": getattr(config, "TRAIL_SL_ENABLED", False) or getattr(config, "OPPOSITE_ORDER_ENABLED", False) or getattr(config, "LIMIT_GUARD", False),
            "runtime": "apply",
            "replay": "partial",
            "note": "Unified S1-S5/S8 path applies Limit Guard, Opposite Order, Trail SL, and SL Guard/Group baseline; SL Guard counts only losing SL/loss-guard closes like runtime",
        },
    ]


def s3_unreplayed_active_features() -> list[dict]:
    return [
        item for item in s3_runtime_feature_coverage()
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
        int(getattr(config, "TF_LOOKBACK", {}).get(tf_name, getattr(config, "SWING_LOOKBACK", 20)) or 20) + 20,
    )
    start_utc = SINCE - timedelta(seconds=TF_SECONDS.get(tf_name, 60) * pad_bars)
    return mt5.copy_rates_range(SYMBOL, tf_val, start_utc, range_end_utc)


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


def _pending_from_result(result: dict, tf_name: str, detect_bar: dict, pattern_override: str | None = None) -> dict:
    signal = result["signal"]
    return {
        "sid": 3,
        "tf": tf_name,
        "signal": signal,
        "side": signal,
        "pattern": pattern_override or result.get("pattern", "S3 DM SP"),
        "entry": round(float(result["entry"]), 2),
        "sl": round(float(result["sl"]), 2),
        "tp": round(float(result["tp"]), 2),
        "detect_time": to_bkk(detect_bar["time"]),
        "detect_time_raw": int(detect_bar["time"]),
    }


def _fill_trade(order: dict, bar: dict) -> dict:
    return {
        **order,
        "entry_time": to_bkk(bar["time"]),
        "entry_time_raw": int(bar["time"]),
        "close_type": "OPEN",
    }


def _confirm_ok(rates: list[dict], signal: str, tf_name: str, tf_secs: int, last_candle_time: int, fallback_start: dict) -> bool:
    lookback_bars = max(
        0,
        int(getattr(config, "S3_CONFIRM_LOOKBACK_BARS", getattr(config, "S2_NORMAL_CONFIRM_LOOKBACK_BARS", 8)) or 0),
    )
    confirm = _find_recent_signal_confirmation(rates, signal, tf_secs, lookback_bars)
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


def _pending_from_maru(mp: dict, tf_name: str, confirm_bar: dict) -> dict:
    direction = mp["direction"]
    pattern = f"ท่าที่ 3 DM SP {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'} — Marubozu"
    return {
        "sid": 3,
        "tf": tf_name,
        "signal": direction,
        "side": direction,
        "pattern": pattern,
        "entry": round(float(mp["entry"]), 2),
        "sl": round(float(mp["sl"]), 2),
        "tp": round(float(mp["tp"]), 2),
        "detect_time": to_bkk(confirm_bar["time"]),
        "detect_time_raw": int(confirm_bar["time"]),
        "source_candle_time": int(mp.get("candle_time", 0) or 0),
        "marubozu_source": mp.get("source", "marubozu"),
    }


def backtest_tf(tf_name: str, tf_val: int, range_end_utc: datetime | None = None) -> list[dict]:
    rates = _fetch_rates(tf_name, tf_val, range_end_utc=range_end_utc)
    if rates is None or len(rates) < 120:
        return []
    bars = _as_records(rates)
    since_ts = int(SINCE.timestamp())
    start_idx = max(80, next((i for i, r in enumerate(bars) if int(r["time"]) >= since_ts), 80))
    tf_secs = int(TF_SECONDS_MAP.get(tf_name, 60))

    trades: list[dict] = []
    pending: list[dict] = []
    open_trades: list[dict] = []
    maru_pending: dict[str, dict] = {}
    fired: set[tuple] = set()
    fallback_start: dict = {}

    for i in range(start_idx, len(bars)):
        bar = bars[i]
        bt = to_bkk(bar["time"])
        h = float(bar["high"])
        l = float(bar["low"])
        full_rates = bars[:i + 1]

        still_pending = []
        for order in pending:
            if order["signal"] == "BUY" and l <= float(order["entry"]):
                trade = _fill_trade(order, bar)
                pd = fill_pdfiboplus_round1(trade, full_rates)
                if pd.get("status") == "fail":
                    trades.append(_close_row(trade, "PD_FAIL", float(bar["close"]), bt))
                else:
                    open_trades.append(trade)
            elif order["signal"] == "SELL" and h >= float(order["entry"]):
                trade = _fill_trade(order, bar)
                pd = fill_pdfiboplus_round1(trade, full_rates)
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

        for key, mp in list(maru_pending.items()):
            if int(bar["time"]) <= int(mp.get("candle_time", 0) or 0):
                continue
            bull_next = float(bar["close"]) > float(bar["open"])
            direction = mp.get("direction")
            color_ok = (direction == "BUY" and bull_next) or (direction == "SELL" and not bull_next)
            if color_ok and _confirm_ok(full_rates, direction, tf_name, tf_secs, int(bar["time"]), fallback_start):
                order = _pending_from_maru(mp, tf_name, bar)
                pd = pending_pdfiboplus_round1(order, full_rates)
                if pd.get("status") == "fail":
                    trades.append(pd_cancel_event(order, order["detect_time"]))
                else:
                    pending.append(order)
            maru_pending.pop(key, None)

        result = strategy_3(full_rates)
        mp = result.get("marubozu_pending")
        if mp:
            key = f"{tf_name}_{mp['candle_time']}_s3maru"
            if key not in maru_pending:
                maru_pending[key] = mp

        signal = result.get("signal")
        if signal not in ("BUY", "SELL"):
            continue
        if not _confirm_ok(full_rates, signal, tf_name, tf_secs, int(bar["time"]), fallback_start):
            continue

        key = (
            int(bar["time"]),
            signal,
            round(float(result.get("entry", 0.0) or 0.0), 2),
            round(float(result.get("sl", 0.0) or 0.0), 2),
            round(float(result.get("tp", 0.0) or 0.0), 2),
            str(result.get("pattern", "")),
        )
        if key in fired:
            continue
        fired.add(key)
        order = _pending_from_result(result, tf_name, bar)
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
