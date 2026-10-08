# -*- coding: utf-8 -*-
"""Live adapter for EA Strategy 2, matching Thirakorn_SMC.mq5."""

from __future__ import annotations

from strategy_ids import ea_comment_meta
import json
import math
import os
from bisect import bisect_right
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ea_strategy_2 import DEFAULT_CFG, LIVE_STATE_VERSION, advance_live_state


BKK = timezone(timedelta(hours=7))
def _bar_dict(bar: Any) -> dict:
    names = ("time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume")
    return {name: bar[name] for name in names if name in getattr(bar, "dtype", ()).names} if hasattr(bar, "dtype") else dict(bar)


def _state_path(cfg) -> Path:
    """Keep state isolated per runtime profile, like the other bot state."""
    profile_dir = Path(getattr(cfg, "PROFILE_DIR", Path(__file__).parent))
    return profile_dir / "ea2_live_state.json"


def _atomic_save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def _load_state(path: Path, symbol: str) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if int(payload.get("version", 0) or 0) != LIVE_STATE_VERSION:
        return None
    if str(payload.get("symbol", "")) != str(symbol):
        return None
    return payload


def _load_latest_state(path: Path, symbol: str) -> dict | None:
    """Prefer EA2 state, but migrate a newer legacy S435 state on first restart."""
    current = _load_state(path, symbol)
    legacy = _load_state(path.with_name("s435_live_state.json"), symbol)
    if legacy is None:
        return current
    if current is None:
        return legacy
    if int(legacy.get("last_bar_time", 0) or 0) > int(current.get("last_bar_time", 0) or 0):
        return legacy
    return current


def _ema(values, period: int) -> float:
    if not values:
        return 0.0
    alpha = 2.0 / (period + 1.0)
    value = float(values[0])
    for item in values[1:]:
        value += alpha * (float(item) - value)
    return value


def _htf_allows(signal: str, rates) -> bool:
    if rates is None or len(rates) < 55:
        return False
    closes = [float(row["close"]) for row in rates]
    fast = _ema(closes[-80:], 20)
    slow = _ema(closes[-120:], 50)
    last = closes[-1]
    return (last > fast >= slow) if signal == "BUY" else (last < fast <= slow)


def _make_htf_filter(rates, decision_bar_seconds: int = 60):
    """Optional research filter using only HTF bars closed by decision time."""
    if rates is None or len(rates) < 55:
        return lambda buy, event_bar, raw_time: False
    rows = list(rates)
    times = [int(row["time"]) for row in rows]
    deltas = [b - a for a, b in zip(times, times[1:]) if b > a]
    htf_seconds = min(deltas) if deltas else 900
    close_times = [raw_time + htf_seconds for raw_time in times]
    closes = [float(row["close"]) for row in rows]
    fast_values = []
    slow_values = []
    fast = slow = closes[0]
    for close in closes:
        fast += (2.0 / 21.0) * (close - fast)
        slow += (2.0 / 51.0) * (close - slow)
        fast_values.append(fast)
        slow_values.append(slow)

    def allows(buy: bool, event_bar: int, raw_time: int) -> bool:
        decision_time = int(raw_time) + int(decision_bar_seconds)
        idx = bisect_right(close_times, decision_time) - 1
        if idx < 54:
            return False
        if buy:
            return closes[idx] > fast_values[idx] >= slow_values[idx]
        return closes[idx] < fast_values[idx] <= slow_values[idx]

    return allows


def _ea2_position(obj: Any, cfg) -> bool:
    magic = int(getattr(cfg, "EA2_MAGIC_NUMBER", 550011) or 550011)
    return (
        int(getattr(obj, "magic", 0) or 0) == magic
        or (ea_comment_meta(getattr(obj, "comment", "")) or (None, None))[1] == "ea2"
    )


def portfolio_guard(mt5, cfg, symbol: str) -> tuple[bool, str]:
    """Match MQ5 ``CountMyPositions``; broker validation handles margin."""
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        return False, "positions unavailable"
    own_positions = [position for position in positions if _ea2_position(position, cfg)]
    max_positions = int(getattr(cfg, "EA2_MAX_POSITIONS", 2) or 0)
    if max_positions > 0 and len(own_positions) >= max_positions:
        return False, f"EA2 exposure limit {len(own_positions)}/{max_positions}"
    return True, "position limit pass"


def _calc_mq5_lot(mt5, cfg, info, account) -> float:
    """Port of MQ5 ``CalcLot(InpSlPoints)`` using balance risk."""
    del mt5
    point = float(getattr(info, "point", 0.0) or 0.0)
    tick_size = float(getattr(info, "trade_tick_size", 0.0) or 0.0)
    tick_value = float(getattr(info, "trade_tick_value", 0.0) or 0.0)
    min_lot = float(getattr(info, "volume_min", 0.01) or 0.01)
    max_lot = float(getattr(info, "volume_max", min_lot) or min_lot)
    step = float(getattr(info, "volume_step", min_lot) or min_lot)
    if point <= 0 or tick_size <= 0 or tick_value <= 0 or step <= 0:
        return min_lot
    risk_money = float(getattr(account, "balance", 0.0) or 0.0) * float(
        getattr(cfg, "EA2_RISK_PERCENT", 1.0)
    ) / 100.0
    money_per_point = (tick_value / tick_size) * point
    sl_money = float(getattr(cfg, "EA2_SL_POINTS", 200)) * money_per_point
    if sl_money <= 0:
        return min_lot
    lot = math.floor((risk_money / sl_money) / step + 1e-12) * step
    lot = max(min_lot, min(lot, max_lot))
    decimals = max(0, min(8, len(f"{step:.8f}".rstrip("0").split(".")[-1])))
    return round(lot, decimals)


def _in_session(now: datetime, start_hour: int, end_hour: int) -> bool:
    hour = now.astimezone(BKK).hour
    if start_hour <= end_hour:
        return start_hour <= hour < end_hour
    return hour >= start_hour or hour < end_hour


def detect_ea2(rates, *, tf: str, mt5, cfg, symbol: str, htf_rates=None) -> dict:
    del htf_rates  # MQ5 analyzes M1 only and has no higher-timeframe filter.
    if tf != str(getattr(cfg, "EA2_LIVE_TF", "M1")).upper():
        return {"signal": "WAIT", "reason": "EA2 ใช้เฉพาะ M1 ตาม MQ5"}
    if rates is None or len(rates) < 510:
        return {"signal": "WAIT", "reason": f"EA2 warm-up ไม่พอ ({0 if rates is None else len(rates)}/510)"}

    tick = mt5.symbol_info_tick(symbol)
    info = mt5.symbol_info(symbol)
    account = mt5.account_info()
    if tick is None or info is None or account is None:
        return {"signal": "WAIT", "reason": "EA2 tick/symbol/account unavailable"}
    point = float(getattr(info, "point", 0.01) or 0.01)
    spread_points = max(0.0, (float(tick.ask) - float(tick.bid)) / point)

    bars = [_bar_dict(row) for row in rates]
    engine_cfg = dict(DEFAULT_CFG)
    engine_cfg["POINT"] = point
    state_path = _state_path(cfg)
    state = _load_latest_state(state_path, symbol)
    state, new_events = advance_live_state(bars, state, engine_cfg)
    pending_events = list(state.get("pending_events", []))
    pending_events.extend(new_events)
    event = pending_events.pop(0) if pending_events else None
    state["pending_events"] = pending_events
    state.update({
        "symbol": symbol, "tf": tf, "saved_at": datetime.now(BKK).isoformat(),
        "spread_points": round(spread_points, 2),
    })
    try:
        _atomic_save(state_path, state)
    except OSError:
        return {"signal": "WAIT", "reason": "EA2 บันทึก state ไม่สำเร็จ"}
    if not event:
        return {"signal": "WAIT", "reason": "EA2 ไม่มี setup ใหม่"}

    now = datetime.now(BKK)
    if not _in_session(
        now,
        int(getattr(cfg, "EA2_SESSION_START_HOUR", 8)),
        int(getattr(cfg, "EA2_SESSION_END_HOUR", 22)),
    ):
        return {"signal": "WAIT", "reason": "EA2 อยู่นอก session 08:00-22:00 BKK"}
    max_spread = float(getattr(cfg, "EA2_MAX_SPREAD_POINTS", 50.0))
    if max_spread > 0 and spread_points > max_spread:
        return {"signal": "WAIT", "reason": f"EA2 spread สูง {spread_points:.1f}>{max_spread:.1f}pt"}
    allowed, guard_reason = portfolio_guard(mt5, cfg, symbol)
    if not allowed:
        return {"signal": "WAIT", "reason": f"EA2 {guard_reason}"}

    signal = str(event["signal"])
    entry = float(tick.ask if signal == "BUY" else tick.bid)
    sl_distance = float(getattr(cfg, "EA2_SL_POINTS", 200)) * point
    tp_distance = float(getattr(cfg, "EA2_TP_POINTS", 600)) * point
    sl = entry - sl_distance if signal == "BUY" else entry + sl_distance
    tp = entry + tp_distance if signal == "BUY" else entry - tp_distance
    lot = _calc_mq5_lot(mt5, cfg, info, account)
    digits = int(getattr(info, "digits", 2) or 2)
    return {
        "signal": signal,
        "entry": round(entry, digits), "sl": round(sl, digits), "tp": round(tp, digits),
        "volume": lot,
        "order_mode": "market", "pattern": "EA2_OB_RETEST",
        "entry_label": "Market ที่",
        "reason": (
            f"EA2 Thirakorn SMC MQ5 | {event['reason']} | "
            f"spread {spread_points:.1f}pt | lot {lot:.2f} | {guard_reason}"
        ),
        "risk": round(sl_distance, digits),
    }
