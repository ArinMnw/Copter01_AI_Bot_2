# -*- coding: utf-8 -*-
"""Live adapter for EA2.1 (M5 entries confirmed by closed M15 bars)."""

from __future__ import annotations

from strategy_ids import ea_comment_meta
import json
import math
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ea_strategy_2_1 import (
    DEFAULT_CFG, LIVE_STATE_VERSION, advance_live_state, make_entry_filter,
)


BKK = timezone(timedelta(hours=7))


def _bar_dict(bar: Any) -> dict:
    names = ("time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume")
    return (
        {name: bar[name] for name in names if name in getattr(bar, "dtype", ()).names}
        if hasattr(bar, "dtype") else dict(bar)
    )


def _state_path(cfg) -> Path:
    profile_dir = Path(getattr(cfg, "PROFILE_DIR", Path(__file__).parent))
    return profile_dir / "ea2_1_live_state.json"


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


def _atomic_save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def _engine_cfg(cfg, point: float) -> dict:
    result = dict(DEFAULT_CFG)
    mapping = {
        "SL_POINTS": "EA2_1_SL_POINTS",
        "TP_POINTS": "EA2_1_TP_POINTS",
        "BREAKEVEN_TRIGGER_POINTS": "EA2_1_BREAKEVEN_TRIGGER_POINTS",
        "BREAKEVEN_LOCK_POINTS": "EA2_1_BREAKEVEN_LOCK_POINTS",
        "TRAIL_TRIGGER_POINTS": "EA2_1_TRAIL_TRIGGER_POINTS",
        "TRAIL_DISTANCE_POINTS": "EA2_1_TRAIL_DISTANCE_POINTS",
        "TRAIL_STEP_POINTS": "EA2_1_TRAIL_STEP_POINTS",
        "MIN_LEG_POINTS": "EA2_1_MIN_LEG_POINTS",
        "OB_PREFER_DEEPER_MAX_POINTS": "EA2_1_OB_PREFER_DEEPER_MAX_POINTS",
        "OB_MAX_BARS_VALID": "EA2_1_OB_MAX_BARS_VALID",
        "COOLDOWN_BARS": "EA2_1_COOLDOWN_BARS",
    }
    for key, attr in mapping.items():
        result[key] = getattr(cfg, attr, result[key])
    result["POINT"] = point
    result["TIMEFRAME_SECONDS"] = 300
    return result


def _own_position(obj: Any, cfg) -> bool:
    magic = int(getattr(cfg, "EA2_1_MAGIC_NUMBER", 550021) or 550021)
    comment = str(getattr(obj, "comment", "")).upper()
    return int(getattr(obj, "magic", 0) or 0) == magic or (ea_comment_meta(comment) or (None, None))[1] == "ea2.1"


def _portfolio_guard(mt5, cfg, symbol: str) -> tuple[bool, str]:
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        return False, "positions unavailable"
    own = [position for position in positions if _own_position(position, cfg)]
    max_positions = int(getattr(cfg, "EA2_1_MAX_POSITIONS", 1) or 0)
    if max_positions > 0 and len(own) >= max_positions:
        return False, f"EA2.1 exposure limit {len(own)}/{max_positions}"
    return True, "position limit pass"


def _calc_lot(cfg, info, account) -> float:
    point = float(getattr(info, "point", 0.0) or 0.0)
    tick_size = float(getattr(info, "trade_tick_size", 0.0) or 0.0)
    tick_value = float(getattr(info, "trade_tick_value", 0.0) or 0.0)
    min_lot = float(getattr(info, "volume_min", 0.01) or 0.01)
    max_lot = float(getattr(info, "volume_max", min_lot) or min_lot)
    step = float(getattr(info, "volume_step", min_lot) or min_lot)
    if point <= 0 or tick_size <= 0 or tick_value <= 0 or step <= 0:
        return min_lot
    risk_money = float(getattr(account, "balance", 0.0) or 0.0) * float(
        getattr(cfg, "EA2_1_RISK_PERCENT", 1.0)
    ) / 100.0
    money_per_point = (tick_value / tick_size) * point
    sl_money = float(getattr(cfg, "EA2_1_SL_POINTS", 1200)) * money_per_point
    lot = math.floor((risk_money / sl_money) / step + 1e-12) * step if sl_money > 0 else min_lot
    lot = max(min_lot, min(lot, max_lot))
    decimals = max(0, min(8, len(f"{step:.8f}".rstrip("0").split(".")[-1])))
    return round(lot, decimals)


def _in_session(now: datetime, start_hour: int, end_hour: int) -> bool:
    hour = now.astimezone(BKK).hour
    return start_hour <= hour < end_hour if start_hour <= end_hour else hour >= start_hour or hour < end_hour


def execution_intent(cfg, symbol):
    return (_load_state(_state_path(cfg), symbol) or {}).get("ea21_execution_intent")


def mark_execution_attempt(cfg, symbol, token, *, volume, broker_time):
    """Persist before sending: an interrupted/ambiguous send must not be retried blindly."""
    state = _load_state(_state_path(cfg), symbol)
    intent = (state or {}).get("ea21_execution_intent")
    if not intent or intent["token"] != token or intent["status"] != "ready":
        raise RuntimeError("EA2.1 execution intent is not ready")
    intent.update(status="inflight", volume=float(volume), broker_time=int(broker_time))
    _atomic_save(_state_path(cfg), state)


def acknowledge_execution(cfg, symbol, token, *, success, uncertain=False, ticket=None):
    state = _load_state(_state_path(cfg), symbol)
    intent = (state or {}).get("ea21_execution_intent")
    if not intent or intent["token"] != token:
        raise RuntimeError("EA2.1 execution acknowledgement does not match intent")
    if success:
        state["entry_done_cycle"] = True
        state["ea21_last_accepted_time"] = int(intent["event"]["bar_time"])
        state["ea21_last_execution_ticket"] = ticket
        state.pop("ea21_execution_intent", None)
    else:
        intent.update(status="unknown" if uncertain else "ready", next_retry=time.time() + 15)
    _atomic_save(_state_path(cfg), state)


def detect_ea2_1(rates, *, tf: str, mt5, cfg, symbol: str, htf_rates=None,
                 defer_execution=False) -> dict:
    live_tf = str(getattr(cfg, "EA2_1_LIVE_TF", "M5")).upper()
    if tf != live_tf:
        return {"signal": "WAIT", "reason": f"EA2.1 ใช้เฉพาะ {live_tf}"}
    if rates is None or len(rates) < 510:
        return {"signal": "WAIT", "reason": "EA2.1 warm-up ไม่พอ"}
    if htf_rates is None or len(htf_rates) < int(DEFAULT_CFG["HTF_EMA_HISTORY_BARS"]):
        return {"signal": "WAIT", "reason": "EA2.1 M15 confirmation ไม่พร้อม"}

    tick = mt5.symbol_info_tick(symbol)
    info = mt5.symbol_info(symbol)
    account = mt5.account_info()
    if tick is None or info is None or account is None:
        return {"signal": "WAIT", "reason": "EA2.1 tick/symbol/account unavailable"}
    point = float(getattr(info, "point", 0.01) or 0.01)
    spread_points = max(0.0, (float(tick.ask) - float(tick.bid)) / point)
    max_spread = float(getattr(cfg, "EA2_1_MAX_SPREAD_POINTS", 25.0))
    if max_spread > 0 and spread_points > max_spread:
        return {"signal": "WAIT", "reason": f"EA2.1 spread {spread_points:.1f}>{max_spread:.1f}pt"}

    engine_cfg = _engine_cfg(cfg, point)
    bars = [_bar_dict(row) for row in rates]
    state_path = _state_path(cfg)
    state = _load_state(state_path, symbol)
    intent = (state or {}).get("ea21_execution_intent") if defer_execution else None
    if intent and intent["status"] in ("inflight", "unknown"):
        return {"signal": "WAIT", "reason": "EA2.1 awaiting broker reconciliation"}
    if intent and int(intent["event"]["bar_time"]) != int(bars[-1]["time"]):
        state.pop("ea21_execution_intent", None)  # Expire unsent setups, never chase old bars.
        intent = None
    if intent and time.time() < float(intent.get("next_retry", 0)):
        return {"signal": "WAIT", "reason": "EA2.1 execution retry cooldown"}
    trend_filter = make_entry_filter(htf_rates, decision_bar_seconds=300, cfg=engine_cfg)
    cooldown_seconds = int(engine_cfg["COOLDOWN_BARS"]) * 300
    last_accepted = int((state or {}).get("ea21_last_accepted_time", 0) or 0)
    rejection_reason = "EA2.1 ไม่มี setup ใหม่"

    def accept_entry(buy, event_bar, raw_time):
        nonlocal last_accepted, rejection_reason
        if intent:
            return False
        if raw_time != int(bars[-1]["time"]):
            return False  # Never submit stale catch-up signals after a restart.
        allowed, reason = _portfolio_guard(mt5, cfg, symbol)
        if not allowed:
            rejection_reason = reason
            return False
        if not _in_session(datetime.now(BKK), int(getattr(cfg, "EA2_1_SESSION_START_HOUR", 0)),
                           int(getattr(cfg, "EA2_1_SESSION_END_HOUR", 24))):
            rejection_reason = "EA2.1 อยู่นอก session"
            return False
        if raw_time - last_accepted < cooldown_seconds:
            rejection_reason = "EA2.1 cooldown"
            return False
        if not trend_filter(buy, event_bar, raw_time):
            rejection_reason = "EA2.1 สัญญาณไม่ผ่าน M15"
            return False
        last_accepted = raw_time
        return True

    state, accepted = advance_live_state(bars, state, engine_cfg, entry_filter=accept_entry)
    previous_accepted = int(state.get("ea21_last_accepted_time", 0) or 0)
    state["ea21_last_accepted_time"] = last_accepted
    pending = [event for event in state.get("ea21_pending_events", [])
               if int(event.get("bar_time", 0)) == int(bars[-1]["time"])]
    pending.extend(accepted)
    event = pending.pop(0) if pending else None
    state["ea21_pending_events"] = pending
    if defer_execution:
        if intent:
            event = intent["event"]
        elif event:
            token = f"{symbol}:{event['bar_time']}:{event['signal']}"
            intent = {"token": token, "event": event, "status": "ready"}
            state["ea21_execution_intent"] = intent
            state["entry_done_cycle"] = False
            state["ea21_last_accepted_time"] = previous_accepted
    state.update({
        "symbol": symbol, "tf": tf, "saved_at": datetime.now(BKK).isoformat(),
        "spread_points": round(spread_points, 2),
    })
    try:
        _atomic_save(state_path, state)
    except OSError:
        return {"signal": "WAIT", "reason": "EA2.1 บันทึก state ไม่สำเร็จ"}
    if event is None:
        return {"signal": "WAIT", "reason": rejection_reason}

    now = datetime.now(BKK)
    start_hour = int(getattr(cfg, "EA2_1_SESSION_START_HOUR", 0))
    end_hour = int(getattr(cfg, "EA2_1_SESSION_END_HOUR", 24))
    if not _in_session(now, start_hour, end_hour):
        return {"signal": "WAIT", "reason": "EA2.1 อยู่นอก session"}
    allowed, guard_reason = _portfolio_guard(mt5, cfg, symbol)
    if not allowed:
        return {"signal": "WAIT", "reason": guard_reason}

    signal = str(event["signal"])
    entry = float(tick.ask if signal == "BUY" else tick.bid)
    sl_distance = float(getattr(cfg, "EA2_1_SL_POINTS", 1200)) * point
    tp_distance = float(getattr(cfg, "EA2_1_TP_POINTS", 5000)) * point
    sl = entry - sl_distance if signal == "BUY" else entry + sl_distance
    tp = entry + tp_distance if signal == "BUY" else entry - tp_distance
    digits = int(getattr(info, "digits", 2) or 2)
    lot = _calc_lot(cfg, info, account)
    return {
        "signal": signal,
        "execution_token": intent["token"] if defer_execution and intent else None,
        "entry": round(entry, digits), "sl": round(sl, digits), "tp": round(tp, digits),
        "volume": lot, "order_mode": "market", "pattern": "EA2_1_M5_M15",
        "entry_label": "Market ที่",
        "reason": (
            f"EA2.1 M5+M15 | {event['reason']} | spread {spread_points:.1f}pt | "
            f"lot {lot:.2f} | {guard_reason}"
        ),
        "risk": round(sl_distance, digits),
    }
