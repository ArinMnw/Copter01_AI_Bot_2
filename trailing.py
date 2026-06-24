from config import *
import config
import re
import inspect
import os
import time
from bot_log import LOG_DIR, log_event, log_error
from mt5_utils import connect_mt5, TF_SECONDS_MAP
from strategy4 import (
    _find_prev_swing_high,
    _find_prev_swing_low,
    _find_prev_pivot_swing_high,
    _find_prev_pivot_swing_low,
    _find_hh,
    _find_ll,
)
from strategy2 import strategy_2
from strategy3 import strategy_3
from strategy11 import reset_state as s11_reset_state

# FVG order quality tracking
fvg_order_tickets: dict = {}

# mapping: ticket -> {tf, gap_bot, gap_top} for limit orders
pending_order_tf: dict = {}   # {ticket: {tf, gap_bot, gap_top}}

# mapping: position ticket -> tf_name (all strategies)
position_tf: dict = {}   # {ticket: tf_name}

# mapping: position ticket -> strategy id
position_sid: dict = {}  # {ticket: 2|3}

# mapping: position ticket -> pattern name
position_pattern: dict = {}  # {ticket: "pattern string"}
position_trend_filter: dict = {}  # {ticket: "bull_strong,sideway"}
position_zone_meta: dict = {}  # {ticket: {"enabled", "signal", "zone_price", "swing_price", "zone_ok_initial"}}
position_forward_meta: dict = {}  # {ticket: {"enabled", "signal", "detect_bar_time", "forward_bars", "confirmed"}}

# Trail SL state per ticket
_trail_state: dict = {}
_trend_filter_last_dir: dict = {}  # {"ticket|tf": "BULL"|"BEAR"|"SIDEWAY"}

# Premium/Discount zone recheck state per pending order ticket
# Format: {ticket: {"signal", "tf", "price", "cur_h", "cur_l", "round1": int}}
# checks[i]: 0 = not yet done, 1 = pass, -1 = fail
_pdfiboplus_state: dict = {}
_pdfiboplus_pending_passed: set[int] = set()  # tickets ที่ผ่าน round2 (pending) แล้ว — ป้องกัน round1 วิ่งซ้ำ
_pdfiboplus_fill_checked: set[int] = set()  # tickets ที่ผ่าน PD Zone fill check ครบทุก round แล้ว
_pdfiboplus_fill_state:   dict     = {}     # {ticket: {tf, signal, fill_h, fill_l, ...}} รอ round 2

# Limit Trend Recheck multi-round state
# {ticket: {"round": int, "rounds_total": int, "cur_h": float, "cur_l": float, "signal": str}}
_trend_recheck_state: dict = {}

# Pending Trend Check on Approach: state per pending order (pre-fill)
# {ticket: {"tf": str, "signal": str,
#            "round1_sh": float|None, "round1_sl": float|None,
#            "round2_start_time": int}}
_pending_trend_approach: dict = {}

# ── Triple Recheck combined state ────────────────────────────────────────────
# {ticket: {"rsi": None|True|False, "trend": None|True|False,
#            "pd": None|True|False, "tf": str, "signal": str}}
# None = ยังไม่ได้เช็ค, True = pass, False = fail
_triple_check_state: dict = {}

# ── SL Guard state ────────────────────────────────────────────────────────────
# {(tf, side): {"count": int, "active": bool, "blocked_since_bar": int,
#               "swing_ref": float}}
# side = "BUY" | "SELL"
_sl_guard_state: dict = {}

# ── SL Guard Combined TF state ──────────────────────────────
# {side: {"count": int, "active": bool,
#         "tf_blocked": {tf: bool},
#         "tf_since": {tf: int},        # timestamp เมื่อ TF นั้นถูกล็อก
#         "tf_swing_ref": {tf: float},  # swing ref ของ TF นั้น (สำหรับ unblock check)
#         "tf_blocked_signals": {tf: list},   # signals รอ retry เมื่อ unblock
# }}
_sl_guard_combined: dict = {}

# ── SL Guard Group state ──────────────────────────────────────
# {side: {group_key: {"count": int, "active": bool,
#          "tf_blocked": {tf: bool}, "tf_since": {tf: int},
#          "tf_swing_ref": {tf: float},
#          "tf_blocked_signals": {tf: list},
#          "tf_retry_signals": {tf: list}}}}
_sl_guard_group: dict = {}  # {symbol: {side: {gkey: sg}}}


def _sl_guard_record_sl(tf: str, side: str, symbol: str = "") -> bool:
    """
    Called from notifications.py when an SL Hit is detected.
    Returns True if the guard was just activated.
    """
    if not tf or not side:
        return False
    sym = (symbol or getattr(config, "SYMBOL", "")).upper()
    key = (sym, tf, side.upper())
    entry = _sl_guard_state.get(key, {"count": 0, "active": False, "blocked_since_bar": 0, "swing_ref": 0.0})
    entry["count"] = entry.get("count", 0) + 1
    just_activated = False
    if config.SL_GUARD_ENABLED and entry["count"] >= config.SL_GUARD_COUNT and not entry.get("active"):
        entry["active"] = True
        entry["blocked_since_bar"] = int(time.time())
        just_activated = True
        # ตั้ง swing_ref ทันทีตอน activate เพื่อป้องกัน _sl_guard_check_unblock
        # deactivate ทันที (swing_ref=0 → condition swing_ref<=0 เป็น True เสมอ)
        try:
            _tick = mt5.symbol_info_tick(SYMBOL)
            if _tick:
                if side.upper() == "SELL":
                    entry["swing_ref"] = float(_tick.ask)   # unblock เมื่อมี high ใหม่เกินนี้
                else:
                    entry["swing_ref"] = float(_tick.bid)   # unblock เมื่อมี low ใหม่ต่ำกว่านี้
        except Exception:
            pass
        log_event("SL_GUARD_ACTIVATE",
                  f"[{tf}] {side.upper()} SL hit {entry['count']}x → guard active | swing_ref={entry.get('swing_ref', 0):.2f}",
                  tf=tf, side=side.upper(), count=entry["count"], swing_ref=entry.get("swing_ref", 0))
        print(f"🛡️ SL Guard ACTIVATED: [{tf}] {side.upper()} ({entry['count']}x SL) swing_ref={entry.get('swing_ref', 0):.2f}")
    _sl_guard_state[key] = entry
    return just_activated


def _sl_guard_cancel_pending_orders(side: str, scope: str = "all", tf: str = "") -> list:
    """
    ยกเลิก pending limit/stop orders เมื่อ SL Guard activate
    scope:
      "tf"       → ยกเลิกเฉพาะ tf+side ที่ระบุ  (per-TF guard)
      "combined" → ยกเลิกทุก pending ของ side ที่อยู่ใน SL_GUARD_COMBINED_TFS
      "all"      → ยกเลิกทุก pending ของ side นั้น ไม่สน TF (Group guard)
    คืน list ticket ที่ยกเลิกสำเร็จ
    """
    if not getattr(config, "SL_GUARD_CLOSE_ON_ACTIVATE", True):
        return []
    try:
        orders = mt5.orders_get(symbol=SYMBOL)
        if not orders:
            return []
        side_up = side.upper()
        buy_types  = (mt5.ORDER_TYPE_BUY_LIMIT,  mt5.ORDER_TYPE_BUY_STOP)
        sell_types = (mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP)
        target_types = buy_types if side_up == "BUY" else sell_types
        combined_tfs = set(getattr(config, "SL_GUARD_COMBINED_TFS", []) or []) if scope == "combined" else None
        cancelled = []
        for order in orders:
            if order.type not in target_types:
                continue
            ticket = int(order.ticket)
            # หา TF จาก pending_order_tf ก่อน แล้ว fallback ไป position_tf
            _info = pending_order_tf.get(ticket)
            order_tf = str((_info.get("tf", "") if isinstance(_info, dict) else "") or position_tf.get(ticket, ""))
            if scope == "tf" and order_tf != tf:
                continue
            if scope == "combined" and combined_tfs and order_tf not in combined_tfs:
                continue
            r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": ticket})
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                cancelled.append(ticket)
                pending_order_tf.pop(ticket, None)
                position_tf.pop(ticket, None)
                position_sid.pop(ticket, None)
                log_event(
                    "SL_GUARD_CANCEL_PENDING",
                    f"ยกเลิก pending {side_up} [{order_tf or tf}] ticket={ticket} scope={scope}",
                    tf=order_tf or tf, side=side_up,
                )
        return cancelled
    except Exception as e:
        print(f"[SL Guard] _sl_guard_cancel_pending_orders error: {e}")
        log_error("SL_GUARD_ERROR", f"cancel_pending: {type(e).__name__}: {e}")
        return []


def _sl_guard_close_open_positions(tf: str, side: str) -> list:
    """
    ปิด position + ยกเลิก pending orders ที่ตรงกับ tf + side เมื่อ SL Guard activate
    คืน list ของ ticket ที่ปิด/ยกเลิกสำเร็จ
    """
    if not getattr(config, "SL_GUARD_CLOSE_ON_ACTIVATE", True):
        return []
    result = []
    try:
        positions = mt5.positions_get(symbol=SYMBOL)
        if positions:
            side_up = side.upper()
            pos_type_mt5 = mt5.ORDER_TYPE_BUY if side_up == "BUY" else mt5.ORDER_TYPE_SELL
            for pos in positions:
                if pos.type != pos_type_mt5:
                    continue
                pos_tf = position_tf.get(pos.ticket, "")
                if pos_tf != tf:
                    continue
                ok, _ = _close_position(pos, side_up, f"SL Guard activate [{tf}]")
                if ok:
                    result.append(pos.ticket)
                    log_event("SL_GUARD_CLOSE", f"ปิด {side_up} [{tf}] ticket={pos.ticket}", tf=tf, side=side_up)
    except Exception as e:
        print(f"[SL Guard] _sl_guard_close_open_positions error: {e}")
        log_error("SL_GUARD_ERROR", f"close_open: {type(e).__name__}: {e}", tf=tf, side=side)
    # ยกเลิก pending orders ของ tf+side เดียวกัน
    result.extend(_sl_guard_cancel_pending_orders(side, scope="tf", tf=tf))
    return result


def _sl_guard_close_combined_positions(side: str) -> list:
    """
    ปิด position + ยกเลิก pending ทั้งหมดของ side นี้ใน SL_GUARD_COMBINED_TFS เมื่อ Combined Guard activate
    คืน list ของ ticket ที่ปิด/ยกเลิกสำเร็จ
    """
    if not getattr(config, "SL_GUARD_CLOSE_ON_ACTIVATE", True):
        return []
    result = []
    try:
        positions = mt5.positions_get(symbol=SYMBOL)
        if positions:
            side_up = side.upper()
            pos_type_mt5 = mt5.ORDER_TYPE_BUY if side_up == "BUY" else mt5.ORDER_TYPE_SELL
            combined_tfs = set(getattr(config, "SL_GUARD_COMBINED_TFS", []) or [])
            for pos in positions:
                if pos.type != pos_type_mt5:
                    continue
                pos_tf = position_tf.get(pos.ticket, "")
                # ถ้ากำหนด combined_tfs ไว้ → กรองเฉพาะ TF ใน group; ถ้าว่าง → ปิดทุก TF
                if combined_tfs and pos_tf not in combined_tfs:
                    continue
                ok, _ = _close_position(pos, side_up, "SL Guard Combined activate")
                if ok:
                    result.append(pos.ticket)
                    log_event("SL_GUARD_CLOSE", f"ปิด {side_up} Combined [{pos_tf}] ticket={pos.ticket}", side=side_up)
    except Exception as e:
        print(f"[SL Guard] _sl_guard_close_combined_positions error: {e}")
        log_error("SL_GUARD_ERROR", f"close_combined: {type(e).__name__}: {e}", side=side)
    # ยกเลิก pending orders ของ combined_tfs+side เดียวกัน
    result.extend(_sl_guard_cancel_pending_orders(side, scope="combined"))
    return result


def _sl_guard_close_all_side_positions(side: str) -> list:
    """
    ปิด position + ยกเลิก pending ทั้งหมดของ side นี้ (ทุก TF ไม่สน group) เมื่อ Group Guard activate
    คืน list ของ ticket ที่ปิด/ยกเลิกสำเร็จ
    """
    if not getattr(config, "SL_GUARD_CLOSE_ON_ACTIVATE", True):
        return []
    result = []
    try:
        positions = mt5.positions_get(symbol=SYMBOL)
        if positions:
            side_up = side.upper()
            pos_type_mt5 = mt5.ORDER_TYPE_BUY if side_up == "BUY" else mt5.ORDER_TYPE_SELL
            for pos in positions:
                if pos.type != pos_type_mt5:
                    continue
                ok, _ = _close_position(pos, side_up, "SL Guard Group activate")
                if ok:
                    result.append(pos.ticket)
                    pos_tf = position_tf.get(pos.ticket, "?")
                    log_event("SL_GUARD_CLOSE", f"ปิด {side_up} Group [{pos_tf}] ticket={pos.ticket}", side=side_up)
    except Exception as e:
        print(f"[SL Guard] _sl_guard_close_all_side_positions error: {e}")
        log_error("SL_GUARD_ERROR", f"close_all_side: {type(e).__name__}: {e}", side=side)
    # ยกเลิก pending orders ทุก TF ของ side นั้น
    result.extend(_sl_guard_cancel_pending_orders(side, scope="all"))
    return result


def _sl_guard_check_unblock(tf: str, side: str, rates, symbol: str = "") -> bool:
    """
    Check whether a new swing L (BUY guard) or swing H (SELL guard) has formed
    AFTER the guard was activated. If yes, deactivate the guard and return True.
    """
    if not config.SL_GUARD_ENABLED:
        return False
    sym = (symbol or getattr(config, "SYMBOL", "")).upper()
    key = (sym, tf, side.upper())
    sg = _sl_guard_state.get(key)
    if not sg or not sg.get("active"):
        return False
    if rates is None or len(rates) < 5:
        return False

    blocked_since = sg.get("blocked_since_bar", 0)
    swing_ref = sg.get("swing_ref", 0.0)

    # Find bars that occurred AFTER guard activation
    # rates["time"] is MT5 server time (UTC+MT5_SERVER_TZ) stored as-if-UTC, so it is
    # numerically (MT5_SERVER_TZ * 3600) seconds ahead of real UTC (time.time()).
    _mt5_tz = getattr(config, "MT5_SERVER_TZ", 1) * 3600
    bars_after = [r for r in rates if int(r["time"]) > blocked_since + _mt5_tz]
    if not bars_after:
        return False

    # ถ้า swing_ref ยังไม่ได้ตั้งค่า (0) ให้ดึงจาก rates แทนที่จะ unblock ทันที
    # (กัน false-unblock ในรอบแรกหลัง activate)
    if swing_ref <= 0:
        if side.upper() == "BUY":
            swing_ref = float(rates[-1]["low"]) if rates is not None and len(rates) > 0 else 0.0
        else:
            swing_ref = float(rates[-1]["high"]) if rates is not None and len(rates) > 0 else 0.0
        sg["swing_ref"] = swing_ref
        _sl_guard_state[key] = sg
        # ยังไม่ unblock — รอให้มีแท่งใหม่หลัง block จริงๆ ก่อน
        if not bars_after:
            return False

    unblock = False
    if side.upper() == "BUY":
        # New Swing Low: any bar after block has lower low than swing_ref
        new_low = min(float(r["low"]) for r in bars_after)
        if new_low < swing_ref:
            unblock = True
    else:  # SELL
        # New Swing High: any bar after block has higher high than swing_ref
        new_high = max(float(r["high"]) for r in bars_after)
        if new_high > swing_ref:
            unblock = True

    if unblock:
        old_count = sg.get("count", 0)
        blocked_signals = sg.get("blocked_signals", [])

        # หา swing bar ที่ trigger unblock (min low สำหรับ BUY, max high สำหรับ SELL)
        if side.upper() == "BUY":
            swing_bar = min(bars_after, key=lambda r: float(r["low"]))
        else:
            swing_bar = max(bars_after, key=lambda r: float(r["high"]))
        swing_bar_time = int(swing_bar["time"])

        # เอาเฉพาะ signal ที่ candle_time หลัง swing bar (signal ก่อน swing → ทิ้ง)
        retry_signals = [
            s for s in blocked_signals
            if (s.get("candle_time") or 0) > swing_bar_time
        ]

        _sl_guard_state[key] = {
            "count": 0, "active": False, "blocked_since_bar": 0, "swing_ref": 0.0,
            "retry_signals": retry_signals,
        }
        print(
            f"🛡️ SL Guard DEACTIVATED: [{tf}] {side.upper()} — "
            f"swing {'L' if side.upper()=='BUY' else 'H'} @ bar {swing_bar_time} "
            f"(was {old_count}x SL, retry {len(retry_signals)}/{len(blocked_signals)} signals)"
        )
        return True
    return False


def _sl_guard_reset_on_tp(tf: str, side: str, symbol: str = "") -> str:
    """
    เรียกเมื่อ position ใดใน TF นั้นโดน TP
    ถ้า SL Guard active → reset count=0, deactivate ทันที (ไม่ต้องรอ swing ใหม่)
    คืน Telegram message ถ้า reset จริง, คืน "" ถ้าไม่มีอะไรทำ
    """
    if not tf or not side:
        return ""
    sym = (symbol or getattr(config, "SYMBOL", "")).upper()
    key = (sym, tf, side.upper())
    sg = _sl_guard_state.get(key)
    if not sg or not sg.get("active"):
        return ""
    old_count = sg.get("count", 0)
    # TP reset: ล้าง blocked_signals ทิ้ง (ไม่มี swing reference → ไม่ retry)
    # scanner จะ pick up signal ใหม่เองในรอบถัดไป
    _sl_guard_state[key] = {
        "count": 0, "active": False, "blocked_since_bar": 0, "swing_ref": 0.0,
    }
    print(f"🛡️ SL Guard RESET by TP: [{tf}] {side.upper()} (was {old_count}x SL, blocked signals cleared)")
    return (
        f"🛡️ *SL Guard รีเซทโดย TP*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📊 TF: `{tf}` | {side.upper()}\n"
        f"✅ TP hit → Guard ปิดทันที (เคย SL {old_count}x)\n"
        f"🔓 กลับมารับ {side.upper()} LIMIT ได้ตามปกติ"
    )


def _sl_guard_get_retry_signals(tf: str, side: str, symbol: str = "") -> list:
    """
    ดึง retry signals ที่ถูก block ไว้ระหว่าง guard active
    เรียกครั้งเดียวแล้ว clear — scanner.py จะ re-place เหล่านี้ทันที
    """
    sym = (symbol or getattr(config, "SYMBOL", "")).upper()
    key = (sym, tf, side.upper())
    sg = _sl_guard_state.get(key)
    if not sg:
        return []
    retries = sg.pop("retry_signals", [])
    if retries:
        _sl_guard_state[key] = sg
    return retries


# ═══════════════════════════════════════════════════════════════
#  SL Guard — Combined TF mode
# ═══════════════════════════════════════════════════════════════

def _combined_guard_record_sl(tf: str, side: str, symbol: str = "") -> str:
    """
    บันทึก SL hit จาก TF นี้เข้า combined counter
    ถ้า count รวม ≥ SL_GUARD_COMBINED_COUNT → ล็อก TF ทั้งหมดใน group
    คืน Telegram message ถ้า guard เพิ่ง activate, ไม่งั้นคืน ""
    """
    if not getattr(config, "SL_GUARD_COMBINED_ENABLED", False):
        return ""
    combined_tfs = list(getattr(config, "SL_GUARD_COMBINED_TFS", []) or [])
    if tf not in combined_tfs:
        return ""

    side = side.upper()
    sym  = (symbol or getattr(config, "SYMBOL", "")).upper()
    sg = _sl_guard_combined.setdefault(sym, {}).setdefault(side, {
        "count": 0, "active": False,
        "tf_blocked": {}, "tf_since": {}, "tf_swing_ref": {},
        "tf_blocked_signals": {},
    })

    # เพิ่ม count และ mark TF นี้ว่ามี SL
    sg["count"] = sg.get("count", 0) + 1
    threshold   = max(1, int(getattr(config, "SL_GUARD_COMBINED_COUNT", 1)))
    just_activated = False

    if sg["count"] >= threshold and not sg.get("active"):
        sg["active"] = True
        # ล็อกทุก TF ใน group ที่ยังไม่ได้ unblock
        ts_now = int(time.time())
        for _t in combined_tfs:
            if not sg["tf_blocked"].get(_t):
                sg["tf_blocked"][_t]        = True
                sg["tf_since"][_t]          = ts_now
                sg["tf_swing_ref"][_t]      = 0.0
                sg.setdefault("tf_blocked_signals", {}).setdefault(_t, [])
        just_activated = True
        print(f"🛡️ Combined Guard ACTIVATED: {side} (count={sg['count']}/{threshold}) — locked {combined_tfs}")

    _sl_guard_combined[sym][side] = sg
    if not just_activated:
        return ""

    tf_list = ", ".join(combined_tfs)
    return (
        f"🛡️ *SL Guard Combined เปิดใช้งาน*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📊 Group TF: `{tf_list}` | {side}\n"
        f"⚠️ SL รวม {sg['count']}x ครบ {threshold}x — ล็อกทุก TF ใน group\n"
        f"⏳ รอ Swing {'Low' if side == 'BUY' else 'High'} ของแต่ละ TF\n"
        f"🔔 Trigger: {tf}"
    )


def _combined_guard_is_blocked(tf: str, side: str, symbol: str = "") -> bool:
    """คืน True ถ้า TF นี้ถูกล็อกโดย Combined Guard"""
    if not getattr(config, "SL_GUARD_COMBINED_ENABLED", False):
        return False
    side = side.upper()
    sym  = (symbol or getattr(config, "SYMBOL", "")).upper()
    sg   = _sl_guard_combined.get(sym, {}).get(side, {})
    return bool(sg.get("active") and sg.get("tf_blocked", {}).get(tf))


def _combined_guard_check_unblock(tf: str, side: str, rates, symbol: str = "") -> bool:
    """
    ตรวจ swing low (BUY) / swing high (SELL) ที่เกิดหลัง lock
    ถ้าเจอ → unblock TF นี้ออกจาก group
    ถ้าทุก TF unblock แล้ว → reset active=False, count=0
    คืน True ถ้า TF นี้เพิ่ง unblock
    """
    if not getattr(config, "SL_GUARD_COMBINED_ENABLED", False):
        return False
    side = side.upper()
    sym  = (symbol or getattr(config, "SYMBOL", "")).upper()
    sg   = _sl_guard_combined.get(sym, {}).get(side, {})
    if not sg or not sg.get("active"):
        return False
    if not sg.get("tf_blocked", {}).get(tf):
        return False
    if rates is None or len(rates) < 5:
        return False

    blocked_since  = sg.get("tf_since", {}).get(tf, 0)
    swing_ref      = sg.get("tf_swing_ref", {}).get(tf, 0.0)

    # init swing_ref ถ้ายังไม่ได้ตั้ง (0) — ใช้ high/low ของแท่งล่าสุด ณ เวลา activate
    if swing_ref <= 0:
        if side == "BUY":
            swing_ref = float(rates[-1]["low"])
        else:
            swing_ref = float(rates[-1]["high"])
        sg.setdefault("tf_swing_ref", {})[tf] = swing_ref
        _sl_guard_combined.setdefault(sym, {})[side] = sg

    # rates["time"] is MT5 server time (UTC+MT5_SERVER_TZ) stored as-if-UTC, so it is
    # numerically (MT5_SERVER_TZ * 3600) seconds ahead of real UTC (time.time()).
    _mt5_tz = getattr(config, "MT5_SERVER_TZ", 1) * 3600
    bars_after     = [r for r in rates if int(r["time"]) > blocked_since + _mt5_tz]
    if not bars_after:
        return False

    unblock = False
    if side == "BUY":
        new_low = min(float(r["low"]) for r in bars_after)
        if new_low < swing_ref:
            unblock = True
    else:
        new_high = max(float(r["high"]) for r in bars_after)
        if new_high > swing_ref:
            unblock = True

    if not unblock:
        return False

    # หา swing bar ที่ trigger unblock
    if side == "BUY":
        swing_bar = min(bars_after, key=lambda r: float(r["low"]))
    else:
        swing_bar = max(bars_after, key=lambda r: float(r["high"]))
    swing_bar_time = int(swing_bar["time"])

    # unblock TF นี้ — เอาเฉพาะ signal ที่ candle_time หลัง swing bar
    blocked_sigs = sg.get("tf_blocked_signals", {}).get(tf, [])
    retry_sigs   = [s for s in blocked_sigs if (s.get("candle_time") or 0) > swing_bar_time]
    sg["tf_blocked"][tf] = False
    sg.setdefault("tf_retry_signals", {})[tf]    = retry_sigs
    sg.setdefault("tf_blocked_signals", {})[tf]  = []
    print(
        f"🛡️ Combined Guard TF unblocked: [{tf}] {side} — "
        f"swing {'L' if side=='BUY' else 'H'} @ bar {swing_bar_time} "
        f"(retry {len(retry_sigs)}/{len(blocked_sigs)} signals)"
    )

    # ถ้าทุก TF ใน group unblock แล้ว → reset สถานะทั้งหมด
    combined_tfs = list(getattr(config, "SL_GUARD_COMBINED_TFS", []) or [])
    all_clear = all(not sg["tf_blocked"].get(t) for t in combined_tfs)
    if all_clear:
        old_count = sg.get("count", 0)
        # เก็บ tf_retry_signals ที่เพิ่งเซตไว้ (รวมจากทุก TF) ก่อน reset
        preserved_retries = {
            t: sg.get("tf_retry_signals", {}).get(t, [])
            for t in combined_tfs
        }
        _sl_guard_combined.setdefault(sym, {})[side] = {
            "count": 0, "active": False,
            "tf_blocked": {}, "tf_since": {}, "tf_swing_ref": {},
            "tf_blocked_signals": {}, "tf_retry_signals": preserved_retries,
        }
        print(f"🛡️ Combined Guard FULLY DEACTIVATED: {side} (all TFs unblocked, was {old_count}x SL)")
    else:
        _sl_guard_combined.setdefault(sym, {})[side] = sg

    return True


def _combined_guard_get_retry_signals(tf: str, side: str, symbol: str = "") -> list:
    """ดึง retry signals ของ TF นี้หลัง unblock (เรียกครั้งเดียวแล้ว clear)"""
    side = side.upper()
    sym  = (symbol or getattr(config, "SYMBOL", "")).upper()
    sg   = _sl_guard_combined.get(sym, {}).get(side, {})
    if not sg:
        return []
    retries = sg.get("tf_retry_signals", {}).pop(tf, [])
    return retries


def _combined_guard_reset_on_tp(tf: str, side: str, symbol: str = "") -> str:
    """
    TP hit → unblock TF นี้ออกจาก combined group ทันที (ไม่รอ swing)
    คืน Telegram message ถ้า unblock จริง
    """
    if not getattr(config, "SL_GUARD_COMBINED_ENABLED", False):
        return ""
    side = side.upper()
    sym  = (symbol or getattr(config, "SYMBOL", "")).upper()
    sg   = _sl_guard_combined.get(sym, {}).get(side, {})
    if not sg or not sg.get("active"):
        return ""
    if not sg.get("tf_blocked", {}).get(tf):
        return ""

    sg["tf_blocked"][tf] = False
    # TP reset: ล้าง blocked_signals ทิ้ง (ไม่มี swing reference → ไม่ retry)
    sg.setdefault("tf_blocked_signals", {})[tf] = []
    sg.setdefault("tf_retry_signals", {})[tf]   = []

    # ถ้าทุก TF clear → reset ทั้งหมด
    combined_tfs = list(getattr(config, "SL_GUARD_COMBINED_TFS", []) or [])
    all_clear    = all(not sg["tf_blocked"].get(t) for t in combined_tfs)
    if all_clear:
        old_count = sg.get("count", 0)
        _sl_guard_combined.setdefault(sym, {})[side] = {
            "count": 0, "active": False,
            "tf_blocked": {}, "tf_since": {}, "tf_swing_ref": {},
            "tf_blocked_signals": {}, "tf_retry_signals": {},
        }
        print(f"🛡️ Combined Guard RESET by TP [{tf}] {side} — all TFs clear (was {old_count}x SL)")
    else:
        _sl_guard_combined.setdefault(sym, {})[side] = sg
        print(f"🛡️ Combined Guard TF reset by TP: [{tf}] {side} — other TFs still locked")

    still_locked = [t for t in combined_tfs if sg.get("tf_blocked", {}).get(t, False)] if not all_clear else []
    locked_str   = f"\n⏳ ยังล็อก: `{'`, `'.join(still_locked)}`" if still_locked else ""
    return (
        f"🛡️ *Combined Guard รีเซทโดย TP*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📊 TF: `{tf}` | {side}\n"
        f"✅ TP hit → `{tf}` unblock ทันที{locked_str}"
    )


# ═══════════════════════════════════════════════════════════════
#  SL Guard — Group mode (ตาม FVG Parallel Group structure)
# ═══════════════════════════════════════════════════════════════

def _get_group_key(group: list) -> str:
    return "+".join(group)


def _group_guard_record_sl(tf: str, side: str, symbol: str = "") -> list:
    """
    บันทึก SL hit จาก TF นี้เข้าทุก group ที่ TF นี้อยู่
    ถ้า count ใน group ≥ SL_GUARD_GROUP_COUNT → ล็อก TF ทั้งหมดใน group นั้น
    คืน list ของ Telegram message สำหรับทุก group ที่เพิ่ง activate
    """
    if not getattr(config, "SL_GUARD_GROUP_ENABLED", False):
        return []
    groups    = list(getattr(config, "SL_GUARD_GROUP_GROUPS", []) or [])
    side      = side.upper()
    sym       = (symbol or getattr(config, "SYMBOL", "")).upper()
    threshold = max(1, int(getattr(config, "SL_GUARD_GROUP_COUNT", 2)))
    ts_now    = int(time.time())
    messages  = []

    for group in groups:
        if tf not in group:
            continue
        gkey   = _get_group_key(group)
        sg_side = _sl_guard_group.setdefault(sym, {}).setdefault(side, {})
        sg = sg_side.setdefault(gkey, {
            "count": 0, "active": False,
            "tf_blocked": {}, "tf_since": {}, "tf_swing_ref": {},
            "tf_swing_bar_time": {},
            "tf_blocked_signals": {}, "tf_retry_signals": {},
        })

        sg["count"] = sg.get("count", 0) + 1

        if sg["count"] >= threshold and not sg.get("active"):
            sg["active"] = True
            for _t in group:
                if not sg["tf_blocked"].get(_t):
                    sg["tf_blocked"][_t]   = True
                    sg["tf_since"][_t]     = ts_now
                    sg["tf_swing_ref"][_t] = 0.0
                    sg.setdefault("tf_blocked_signals", {}).setdefault(_t, [])
            # log_event ก่อน print (print อาจ UnicodeEncodeError บน Windows console)
            log_event("SL_GUARD_GROUP_ACTIVATE",
                      f"{side} group=[{gkey}] SL {sg['count']}x/{threshold}x -> lock {len(group)} TF",
                      side=side, group=gkey, count=sg["count"], trigger_tf=tf)
            try:
                print(f"[SL_GUARD] Group Guard ACTIVATED: {side} group=[{gkey}] (count={sg['count']}/{threshold})")
            except Exception:
                pass
            tf_list = ", ".join(group)
            messages.append((
                f"*SL Guard Group ON*\n"
                f"Group: `{tf_list}` | {side}\n"
                f"SL {sg['count']}x/{threshold}x - lock TF in group\n"
                f"Wait Swing {'Low' if side == 'BUY' else 'High'} each TF\n"
                f"Trigger: {tf}"
            ))

        sg_side[gkey] = sg
        _sl_guard_group[sym][side] = sg_side

    return messages


def _group_guard_is_blocked(tf: str, side: str, symbol: str = "") -> bool:
    """คืน True ถ้า TF นี้ถูกล็อกโดย Group Guard ใด group หนึ่ง"""
    if not getattr(config, "SL_GUARD_GROUP_ENABLED", False):
        return False
    side = side.upper()
    sym  = (symbol or getattr(config, "SYMBOL", "")).upper()
    for sg in _sl_guard_group.get(sym, {}).get(side, {}).values():
        if sg.get("active") and sg.get("tf_blocked", {}).get(tf):
            return True
    return False


_TF_SECONDS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "H12": 43200, "D1": 86400,
}


def _group_guard_check_unblock(tf: str, side: str, rates, symbol: str = "") -> bool:
    """
    ตรวจ swing low (BUY) / swing high (SELL) ที่เกิดหลัง lock
    swing ต้องได้รับการยืนยันด้วย SL_GUARD_GROUP_SWING_BARS แท่งหลังจาก swing bar
    ถ้าเจอ → unblock TF นี้ออกจากทุก group ที่ block อยู่
    คืน True ถ้า unblock อย่างน้อย 1 group
    """
    if not getattr(config, "SL_GUARD_GROUP_ENABLED", False):
        return False
    side = side.upper()
    sym  = (symbol or getattr(config, "SYMBOL", "")).upper()
    sg_side = _sl_guard_group.get(sym, {}).get(side, {})
    if not sg_side or rates is None or len(rates) < 5:
        return False

    confirm_bars = max(1, int(getattr(config, "SL_GUARD_GROUP_SWING_BARS", 5)))
    tf_secs      = _TF_SECONDS.get(tf.upper(), 60)
    latest_bar_time = int(rates[-1]["time"]) if len(rates) > 0 else 0

    did_unblock = False
    for gkey, sg in sg_side.items():
        if not sg.get("active") or not sg.get("tf_blocked", {}).get(tf):
            continue

        blocked_since = sg.get("tf_since", {}).get(tf, 0)

        swing_ref = sg.get("tf_swing_ref", {}).get(tf, 0.0)
        # init swing_ref ถ้ายังไม่ได้ตั้ง (0) — ใช้ high/low ของแท่งล่าสุด ณ เวลา activate
        # (ไม่ใช้ max/min ทั้ง lookback เพราะทำให้ต้องรอทะลุ historical high ก่อนถึง unblock)
        if swing_ref <= 0:
            if side == "BUY":
                swing_ref = float(rates[-1]["low"])
            else:
                swing_ref = float(rates[-1]["high"])
            sg.setdefault("tf_swing_ref", {})[tf] = swing_ref
            sg_side[gkey] = sg

        # rates["time"] is MT5 server time (UTC+MT5_SERVER_TZ) stored as-if-UTC, so it is
        # numerically (MT5_SERVER_TZ * 3600) seconds ahead of real UTC (time.time()).
        _mt5_tz = getattr(config, "MT5_SERVER_TZ", 1) * 3600
        bars_after = [r for r in rates if int(r["time"]) > blocked_since + _mt5_tz]
        if not bars_after:
            continue

        # หา swing bar ที่เกิดขึ้นแล้ว (ยังไม่ตัดสินว่า confirm หรือยัง)
        if side == "BUY":
            candidate = min(bars_after, key=lambda r: float(r["low"]))
            swing_found = float(candidate["low"]) < swing_ref
        else:
            candidate = max(bars_after, key=lambda r: float(r["high"]))
            swing_found = float(candidate["high"]) > swing_ref

        if not swing_found:
            # ยังไม่เจอ swing ใหม่เลย — ล้าง pending ถ้ามี
            sg.get("tf_swing_bar_time", {}).pop(tf, None)
            continue

        swing_bar_time = int(candidate["time"])

        # บันทึก swing bar time ครั้งแรกที่เจอ (หรืออัปเดตถ้า swing ใหม่ดีกว่า)
        prev_swing = sg.setdefault("tf_swing_bar_time", {}).get(tf, 0)
        if swing_bar_time != prev_swing:
            sg["tf_swing_bar_time"][tf] = swing_bar_time

        # รอจนแท่งที่ confirm_bars นับรวม swing bar ปิด
        # (swing bar = bar #1 ดังนั้นรอแค่ confirm_bars-1 แท่งหลัง swing)
        confirm_time = swing_bar_time + (confirm_bars - 1) * tf_secs
        if latest_bar_time < confirm_time:
            continue

        blocked_sigs = sg.get("tf_blocked_signals", {}).get(tf, [])
        retry_sigs   = [s for s in blocked_sigs if (s.get("candle_time") or 0) >= swing_bar_time]
        sg["tf_blocked"][tf] = False
        sg["tf_swing_bar_time"].pop(tf, None)
        sg.setdefault("tf_retry_signals", {})[tf]   = retry_sigs
        sg.setdefault("tf_blocked_signals", {})[tf] = []
        did_unblock = True
        log_event("SL_GUARD_GROUP_UNBLOCK",
                  f"{side} [{tf}] group=[{gkey}] swing confirmed retry={len(retry_sigs)}/{len(blocked_sigs)}",
                  side=side, tf=tf, group=gkey, swing_bar_time=swing_bar_time, confirm_time=confirm_time)
        try:
            print(
                f"[SL_GUARD] Group Guard TF unblocked: [{tf}] {side} group=[{gkey}] "
                f"swing {'L' if side=='BUY' else 'H'} @ bar {swing_bar_time} confirmed @ {confirm_time} "
                f"(retry {len(retry_sigs)}/{len(blocked_sigs)})"
            )
        except Exception:
            pass

        group_tfs = gkey.split("+")
        all_clear = all(not sg["tf_blocked"].get(t) for t in group_tfs)
        if all_clear:
            preserved = {t: sg.get("tf_retry_signals", {}).get(t, []) for t in group_tfs}
            sg_side[gkey] = {
                "count": 0, "active": False,
                "tf_blocked": {}, "tf_since": {}, "tf_swing_ref": {},
                "tf_swing_bar_time": {},
                "tf_blocked_signals": {}, "tf_retry_signals": preserved,
            }
            log_event("SL_GUARD_GROUP_RESET",
                      f"{side} group=[{gkey}] fully unblocked",
                      side=side, group=gkey)
            try:
                print(f"[SL_GUARD] Group Guard group [{gkey}] {side} fully unblocked - reset")
            except Exception:
                pass

    return did_unblock


def _group_guard_get_retry_signals(tf: str, side: str, symbol: str = "") -> list:
    """ดึง retry signals ของ TF นี้จากทุก group หลัง unblock (เรียกครั้งเดียวแล้ว clear)"""
    side = side.upper()
    sym  = (symbol or getattr(config, "SYMBOL", "")).upper()
    result = []
    seen = set()
    for sg in _sl_guard_group.get(sym, {}).get(side, {}).values():
        for sig in sg.get("tf_retry_signals", {}).pop(tf, []):
            key = (sig.get("candle_time", 0), sig.get("sid", 0))
            if key not in seen:
                seen.add(key)
                result.append(sig)
    return result


def _group_guard_reset_on_tp(tf: str, side: str, symbol: str = "") -> str:
    """
    TP hit → unblock TF นี้ออกจากทุก group ทันที (ไม่รอ swing)
    คืน Telegram message ถ้า unblock จริง
    """
    if not getattr(config, "SL_GUARD_GROUP_ENABLED", False):
        return ""
    side    = side.upper()
    sym     = (symbol or getattr(config, "SYMBOL", "")).upper()
    sg_side = _sl_guard_group.get(sym, {}).get(side, {})
    unblocked = []

    for gkey, sg in sg_side.items():
        if not sg.get("active") or not sg.get("tf_blocked", {}).get(tf):
            continue
        sg["tf_blocked"][tf] = False
        sg.setdefault("tf_blocked_signals", {})[tf] = []
        sg.setdefault("tf_retry_signals", {})[tf]   = []
        unblocked.append(gkey)

        group_tfs = gkey.split("+")
        if all(not sg["tf_blocked"].get(t) for t in group_tfs):
            sg_side[gkey] = {
                "count": 0, "active": False,
                "tf_blocked": {}, "tf_since": {}, "tf_swing_ref": {},
                "tf_swing_bar_time": {},
                "tf_blocked_signals": {}, "tf_retry_signals": {},
            }

    if not unblocked:
        return ""
    grp_str = ", ".join(f"[{g}]" for g in unblocked)
    return (
        f"✅ *Group Guard: TP Reset*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📊 [{tf}] {side} TP hit → unblock {grp_str}"
    )


def _group_guard_get_blocked_groups(tf: str, side: str, symbol: str = "") -> list:
    """คืน list ของ group_key ที่ TF นี้ถูก block อยู่ (ใช้แสดงใน scanner log)"""
    side = side.upper()
    sym  = (symbol or getattr(config, "SYMBOL", "")).upper()
    return [
        gkey for gkey, sg in _sl_guard_group.get(sym, {}).get(side, {}).items()
        if sg.get("active") and sg.get("tf_blocked", {}).get(tf)
    ]


def _triple_check_all_enabled() -> bool:
    """True เมื่อ mode = combined และเปิดครบทั้ง 3 check"""
    if not getattr(config, "RECHECK_COMBINED_MODE", False):
        return False
    return (
        getattr(config, "PDFIBOPLUS_ENABLED",       False) and
        getattr(config, "LIMIT_TREND_RECHECK",          False) and
        getattr(config, "PENDING_RSI_RECHECK_ENABLED", False)
    )


def _triple_check_record(ticket: int, key: str, result: bool,
                          tf: str = "", signal: str = "") -> None:
    """บันทึกผล check ของ key ('rsi'|'trend'|'pd') ลงใน state"""
    if ticket not in _triple_check_state:
        _triple_check_state[ticket] = {
            "rsi": None, "trend": None, "pd": None,
            "tf": tf, "signal": signal,
        }
    _triple_check_state[ticket][key] = result


def _triple_r(v) -> str:
    """แสดงสถานะ check เป็น emoji"""
    if v is True:  return "✅"
    if v is False: return "❌"
    return "⏳"


def _triple_check_evaluate(ticket: int) -> str:
    """Return 'cancel' | 'keep' | 'wait'"""
    state = _triple_check_state.get(ticket)
    if not state:
        return "wait"
    vals   = [state["rsi"], state["trend"], state["pd"]]
    passes = sum(1 for v in vals if v is True)
    fails  = sum(1 for v in vals if v is False)
    if fails  >= 2: return "cancel"
    if passes >= 2: return "keep"
    return "wait"


# Rule 4: count bars after order entry
_bar_count: dict = {}

# Rule 5: entry candle state
_entry_state: dict = {}   # {ticket: "done" | "waiting_next"}

# Fill notification tracking
_fill_notified: dict = {}        # {ticket: True} if fill was already notified
_entry_bar_notified: dict = {}   # {ticket: True} if entry candle close was already notified
_fill_initialized: bool = False  # True after first pre-populate of _fill_notified
_entry_bar_none_first: dict = {} # {ticket: monotonic_time} first time entry_bar=None
_reverse_tickets: set = set()    # tickets opened from reverse logic
_FILL_INIT_SUPPRESS_SEC = 180    # suppress fill notify only for positions older than this on init
_last_meta_map_key = ""
_last_trail_tg_key = ""
SLTP_AUDIT_DIR = os.path.join(LOG_DIR, "debug")
SLTP_AUDIT_FILE = os.path.join(SLTP_AUDIT_DIR, "sltp_audit.log")
_last_sltp_cmd_key = ""
_last_sltp_tg_key = ""
_closed_sltp_summary_sent: set[int] = set()
_sl_protect_applied: set[int] = set()
_last_sl_protect_tg_key = ""
_s8_fill_sl: dict = {}   # {ticket: intended_sl} for S8 that filled before SL arm
_fill_rsi_checked: set[int] = set()
_pending_rsi_close: dict = {}          # {ticket: pos_type} — close fail → retry ทุกรอบสแกน
_fill_trend_checked: set[int] = set()  # tickets ที่ผ่าน round1 trend recheck แล้ว

# Strategy 6: 2 High 2 Low trail state
# {ticket: {
#   "swing_h": float,        current swing high to watch
#   "phase": "wait"|"count", wait=touch not reached, count=bar counting 1-5
#   "count": int,
#   "last_bar_time": int,
#   "trail_count": int,      number of completed trail rounds
# }}
_s6_state: dict = {}

# Strategy 6 Independent: trail all positions, not limited to strategy 2/3
_s6i_state: dict = {}

# Limit Sweep: track last checked bar per ticket
_sweep_last_bar: dict = {}  # {ticket: last_checked_bar_time}

# Focus Opposite: frozen_side marker per feature
# "trail_sl"     -> used by check_engulf_trail_sl / SL protect
# "entry_candle" -> used by check_entry_candle_quality
# value: "BUY" | "SELL" | None
_focus_frozen_side: dict = {"trail_sl": None, "entry_candle": None}


def _get_s6_prev_swing_high(rates, lookback=100, tf=""):
    """Swing High สำหรับ S6/S6i — ใช้ HHLL ก่อน fallback pivot/simple"""
    if tf:
        try:
            from hhll_swing import get_swing_hl_pts
            sh_pt, _ = get_swing_hl_pts(tf)
            if sh_pt:
                return {"price": float(sh_pt["price"]), "time": int(sh_pt["time"])}
        except Exception:
            pass
    left = max(1, int(getattr(config, "SWING_PIVOT_LEFT", 15) or 15))
    right = max(1, int(getattr(config, "SWING_PIVOT_RIGHT", 10) or 10))
    return _find_prev_pivot_swing_high(rates, lookback=lookback, left=left, right=right) or _find_prev_swing_high(rates, lookback=lookback)


def _get_s6_prev_swing_low(rates, lookback=100, tf=""):
    """Swing Low สำหรับ S6/S6i — ใช้ HHLL ก่อน fallback pivot/simple"""
    if tf:
        try:
            from hhll_swing import get_swing_hl_pts
            _, sl_pt = get_swing_hl_pts(tf)
            if sl_pt:
                return {"price": float(sl_pt["price"]), "time": int(sl_pt["time"])}
        except Exception:
            pass
    left = max(1, int(getattr(config, "SWING_PIVOT_LEFT", 15) or 15))
    right = max(1, int(getattr(config, "SWING_PIVOT_RIGHT", 10) or 10))
    return _find_prev_pivot_swing_low(rates, lookback=lookback, left=left, right=right) or _find_prev_swing_low(rates, lookback=lookback)


def _short_flow_id(flow_id: str) -> str:
    if not flow_id:
        return ""
    parts = [p for p in str(flow_id).split("|") if p]
    if len(parts) <= 4:
        return "-".join(parts)
    head = parts[:4]
    model = next((p for p in parts[4:] if p.startswith("M")), "")
    if model:
        head.append(model)
    return "-".join(head)


def _parse_bot_comment(comment: str):
    """Parse comment like M1_S2, H4_S3, M1_S6i_buy -> (tf, sid)."""
    if not comment:
        return None, None
    m = re.match(r"(\[[\w-]+\]|M\d+|H\d+|D\d+)(?:_S(\w+))?", comment)
    if not m:
        return None, None
    tf = m.group(1)
    sid_raw = m.group(2)
    if sid_raw is None:
        return tf, None
    if sid_raw == "6i":
        return tf, 7
    m_sid = re.match(r"(\d+)", sid_raw)
    if m_sid:
        try:
            return tf, int(m_sid.group(1))
        except ValueError:
            return tf, None
    try:
        return tf, int(sid_raw)
    except ValueError:
        return tf, None


def _infer_position_meta_from_comment(pos):
    """Infer tf/sid from position comment or entry deal history."""
    tf = sid = None

    pos_comment = getattr(pos, "comment", "") or ""
    tf, sid = _parse_bot_comment(pos_comment)
    if tf or sid is not None:
        return tf, sid, "position_comment"

    try:
        deals = mt5.history_deals_get(position=pos.ticket)
    except Exception:
        deals = None

    if deals:
        entry_deal = sorted(deals, key=lambda d: d.time)[0]
        deal_comment = getattr(entry_deal, "comment", "") or ""
        tf, sid = _parse_bot_comment(deal_comment)
        if tf or sid is not None:
            return tf, sid, "deal_history"

    return None, None, None


def _pending_order_side(order) -> str:
    if order.type in (mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP):
        return "BUY"
    if order.type in (mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP):
        return "SELL"
    return ""


def _pending_order_type_name(order) -> str:
    return {
        mt5.ORDER_TYPE_BUY_LIMIT: "BUY LIMIT",
        mt5.ORDER_TYPE_BUY_STOP: "BUY STOP",
        mt5.ORDER_TYPE_SELL_LIMIT: "SELL LIMIT",
        mt5.ORDER_TYPE_SELL_STOP: "SELL STOP",
    }.get(order.type, "PENDING")


def _pending_order_icon(order) -> str:
    return "🟢" if _pending_order_side(order) == "BUY" else "🔴"


def _latest_pending_rsi(tf: str) -> float | None:
    period = max(2, int(getattr(config, "PENDING_RSI_PERIOD", 14) or 14))
    tf_val = TF_OPTIONS.get(tf, mt5.TIMEFRAME_M1)
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, period + 40)
    if rates is None or len(rates) <= period:
        return None
    try:
        from strategy9 import _calc_rsi_values

        rsi_values = _calc_rsi_values(
            rates,
            period=period,
            applied_price=getattr(config, "PENDING_RSI_APPLIED_PRICE", "close"),
        )
        for value in reversed(rsi_values):
            if value is not None:
                return float(value)
    except Exception as e:
        log_event("PENDING_RSI_RECHECK_ERROR", str(e), tf=tf)
    return None


def _pending_rsi_rule_result(side: str, tf: str) -> dict | None:
    if side not in ("BUY", "SELL"):
        return None

    rsi_value = _latest_pending_rsi(tf)
    if rsi_value is None:
        return None

    if side == "BUY":
        threshold = float(getattr(config, "PENDING_RSI_BUY_MAX", 50.0))
        allowed = rsi_value < threshold
        rule = f"RSI<{threshold:g}"
    else:
        threshold = float(getattr(config, "PENDING_RSI_SELL_MIN", 50.0))
        allowed = rsi_value > threshold
        rule = f"RSI>{threshold:g}"

    return {
        "rsi": float(rsi_value),
        "threshold": threshold,
        "allowed": bool(allowed),
        "rule": rule,
        "threshold_text": f"{threshold:.2f}",
    }


# -------------------------------------------------------------
def _rsi2_get_state(tf: str) -> str:
    """
    Mode 2: หา RSI state จาก crossover ล่าสุดใน history
    Returns: "SELL_ONLY" | "BUY_ONLY" | "ANY"

    Rules (scan จากแท่งล่าสุดย้อนหลัง หยุดที่ event แรกที่เจอ):
      RSI > OB (ปัจจุบัน)          → SELL_ONLY  (absolute rule 5)
      cross ลงจาก OB (prev>OB, cur<OB)  → SELL_ONLY
      cross ลงจาก MID (prev>MID, cur<MID) → SELL_ONLY
      cross ขึ้นจาก OS (prev<OS, cur>OS)  → BUY_ONLY
      cross ขึ้นจาก MID (prev<MID, cur>MID) → BUY_ONLY
    """
    period = max(2, int(getattr(config, "PENDING_RSI_PERIOD", 14) or 14))
    ob  = float(getattr(config, "RSI_MODE2_OB",  70.0))
    os_ = float(getattr(config, "RSI_MODE2_OS",  30.0))
    mid = float(getattr(config, "RSI_MODE2_MID", 50.0))

    tf_val = TF_OPTIONS.get(tf, mt5.TIMEFRAME_M1)
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, period + 60)
    if rates is None or len(rates) <= period:
        return "ANY"
    try:
        from strategy9 import _calc_rsi_values
        rsi_values = _calc_rsi_values(
            rates, period=period,
            applied_price=getattr(config, "PENDING_RSI_APPLIED_PRICE", "close"),
        )
        vals = [v for v in rsi_values if v is not None]
        if not vals:
            return "ANY"

        # Rule 5: RSI > OB absolute → SELL_ONLY เสมอ
        if vals[-1] > ob:
            return "SELL_ONLY"

        # สแกนจากแท่งล่าสุดย้อนหลัง หยุดที่ crossover แรกที่เจอ
        for i in range(len(vals) - 1, 0, -1):
            cur  = vals[i]
            prev = vals[i - 1]
            # cross ลงจาก OB
            if prev > ob and cur <= ob:
                return "SELL_ONLY"
            # cross ลงจาก MID
            if prev >= mid and cur < mid:
                return "SELL_ONLY"
            # cross ขึ้นจาก OS
            if prev <= os_ and cur > os_:
                return "BUY_ONLY"
            # cross ขึ้นจาก MID
            if prev < mid and cur >= mid:
                return "BUY_ONLY"

        return "ANY"
    except Exception as e:
        log_event("RSI2_STATE_ERROR", str(e), tf=tf)
        return "ANY"


def _pending_rsi_mode2_result(side: str, tf: str) -> dict | None:
    """
    Mode 2 RSI Recheck — state machine crossover
    BUY  fill: ต้องการ state != SELL_ONLY
    SELL fill: ต้องการ state != BUY_ONLY
    """
    if side not in ("BUY", "SELL"):
        return None

    rsi_value = _latest_pending_rsi(tf)
    if rsi_value is None:
        return None

    ob  = float(getattr(config, "RSI_MODE2_OB",  70.0))
    os_ = float(getattr(config, "RSI_MODE2_OS",  30.0))
    mid = float(getattr(config, "RSI_MODE2_MID", 50.0))

    state = _rsi2_get_state(tf)

    if side == "BUY":
        allowed = (state != "SELL_ONLY")
        rule    = f"Mode2 BUY block=SELL_ONLY state={state}"
    else:
        allowed = (state != "BUY_ONLY")
        rule    = f"Mode2 SELL block=BUY_ONLY state={state}"

    return {
        "rsi":            float(rsi_value),
        "state":          state,
        "allowed":        bool(allowed),
        "rule":           rule,
        "threshold_text": f"OB={ob:g}/MID={mid:g}/OS={os_:g}",
    }


# -------------------------------------------------------------
def _get_filling_mode():
    """Return the first supported broker fill type (IOC -> FOK -> RETURN)."""
    sym = mt5.symbol_info(SYMBOL)
    if sym:
        fm = sym.filling_mode
        if fm & 2: return mt5.ORDER_FILLING_IOC
        if fm & 1: return mt5.ORDER_FILLING_FOK
    return mt5.ORDER_FILLING_RETURN


def _append_sltp_audit(line: str) -> None:
    if not getattr(config, "SLTP_AUDIT_DEBUG", False):
        return
    try:
        os.makedirs(SLTP_AUDIT_DIR, exist_ok=True)
        with open(SLTP_AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ SLTP audit write error: {e}")
        log_error("SLTP_AUDIT_ERROR", f"{type(e).__name__}: {e}")


def _sltp_dedup_key(source: str, pos, old_sl: float, old_tp: float,
                    new_sl: float, new_tp: float, ok: bool) -> str:
    pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
    return (
        f"{source}|{pos.ticket}|{pos_type}|"
        f"{float(old_sl):.2f}|{float(old_tp):.2f}|"
        f"{float(new_sl):.2f}|{float(new_tp):.2f}|{ok}"
    )


def _audit_sltp_event(source: str, pos, old_sl: float, old_tp: float,
                      new_sl: float, new_tp: float, ok: bool, result=None) -> None:
    if not getattr(config, "SLTP_AUDIT_DEBUG", False):
        return
    global _last_sltp_cmd_key
    tick = mt5.symbol_info_tick(SYMBOL)
    bid = float(getattr(tick, "bid", 0.0)) if tick else 0.0
    ask = float(getattr(tick, "ask", 0.0)) if tick else 0.0
    spread = round(ask - bid, 2) if tick else 0.0
    retcode = getattr(result, "retcode", None) if result is not None else None
    comment = getattr(result, "comment", "") if result is not None else ""
    pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
    line = (
        f"[{now_bkk().strftime('%Y-%m-%d %H:%M:%S')}] source={source} "
        f"ticket={pos.ticket} type={pos_type} entry={float(pos.price_open):.2f} "
        f"old_sl={float(old_sl):.2f} old_tp={float(old_tp):.2f} "
        f"new_sl={float(new_sl):.2f} new_tp={float(new_tp):.2f} "
        f"bid={bid:.2f} ask={ask:.2f} spread={spread:.2f} ok={ok} retcode={retcode} comment={comment}"
    )
    _append_sltp_audit(line)
    key = _sltp_dedup_key(source, pos, old_sl, old_tp, new_sl, new_tp, ok)
    if key != _last_sltp_cmd_key:
        print(f"[{now_bkk().strftime('%H:%M:%S')}] SLTP_AUDIT {line}")
        _last_sltp_cmd_key = key


async def _notify_sltp_audit(app, source: str, pos, old_sl: float, old_tp: float,
                             new_sl: float, new_tp: float, ok: bool):
    return await _notify_sltp_audit_v2(app, source, pos, old_sl, old_tp, new_sl, new_tp, ok)
    global _last_sltp_tg_key
    key = _sltp_dedup_key(source, pos, old_sl, old_tp, new_sl, new_tp, ok)
    if key == _last_sltp_tg_key:
        return
    pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
    sig_e = "🟢" if pos_type == "BUY" else "🔴"
    status = "สำเร็จ" if ok else "ไม่สำเร็จ"
    await tg(app, (
        f"🧾 *SL/TP Update {status}*\n"
        f"{sig_e} Ticket:`{pos.ticket}` [{pos_type}]\n"
        f"Source: `{source}`\n"
        f"SL: `{old_sl:.2f}` -> `{new_sl:.2f}`\n"
        f"TP: `{old_tp:.2f}` -> `{new_tp:.2f}`"
    ))
    _last_sltp_tg_key = key


async def _notify_sltp_audit_v2(app, source: str, pos, old_sl: float, old_tp: float,
                                new_sl: float, new_tp: float, ok: bool):
    if not getattr(config, "SLTP_AUDIT_DEBUG", False):
        return
    global _last_sltp_tg_key, _closed_sltp_summary_sent
    key = _sltp_dedup_key(source, pos, old_sl, old_tp, new_sl, new_tp, ok)
    if key == _last_sltp_tg_key:
        return

    pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
    sig_e = "🟢" if pos_type == "BUY" else "🔴"
    status = "สำเร็จ" if ok else "ไม่สำเร็จ"
    event_time = now_bkk().strftime("%H:%M:%S %d/%m/%Y")
    still_open = bool(mt5.positions_get(ticket=pos.ticket))

    if not still_open:
        if pos.ticket in _closed_sltp_summary_sent:
            return
        await tg(app, (
            f"🧾 *SL/TP Update Summary ({status})*\n"
            f"{sig_e} Ticket:`{pos.ticket}` [{pos_type}]\n"
            f"Event Time: `{event_time}`\n"
            f"Source: `{source}`\n"
            f"SL: `{old_sl:.2f}` -> `{new_sl:.2f}`\n"
            f"TP: `{old_tp:.2f}` -> `{new_tp:.2f}`\n"
            f"Status: `order already closed`"
        ))
        _closed_sltp_summary_sent.add(pos.ticket)
        _last_sltp_tg_key = key
        return

    await tg(app, (
        f"🧾 *SL/TP Update {status}*\n"
        f"{sig_e} Ticket:`{pos.ticket}` [{pos_type}]\n"
        f"Event Time: `{event_time}`\n"
        f"Source: `{source}`\n"
        f"SL: `{old_sl:.2f}` -> `{new_sl:.2f}`\n"
        f"TP: `{old_tp:.2f}` -> `{new_tp:.2f}`"
    ))
    _last_sltp_tg_key = key


# ============================================================
#  Triple Scale-Out (TSO) — Partial close watcher + cleanup
# ============================================================
def _tso_close_partial(pos, pos_type: str, volume: float, reason: str) -> bool:
    """ปิด lot บางส่วนของ position (partial close) — return True ถ้าสำเร็จ"""
    tick = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        return False
    bid = float(getattr(tick, "bid", 0.0))
    ask = float(getattr(tick, "ask", 0.0))
    close_price = bid if pos_type == "BUY" else ask
    info = mt5.symbol_info(SYMBOL)
    try:
        vol_min  = float(getattr(info, "volume_min", 0.01) or 0.01)
        vol_step = float(getattr(info, "volume_step", 0.01) or 0.01)
        # round ลง step + ไม่ต่ำกว่า min
        steps = max(1, int(round(volume / vol_step)))
        send_vol = round(steps * vol_step, 2)
        if send_vol < vol_min:
            send_vol = vol_min
    except Exception:
        send_vol = volume
    # ไม่เกิน volume ปัจจุบันของ position
    send_vol = min(send_vol, float(pos.volume))
    r = mt5.order_send({
        "action":        mt5.TRADE_ACTION_DEAL,
        "symbol":        SYMBOL,
        "volume":        send_vol,
        "type":          mt5.ORDER_TYPE_SELL if pos_type == "BUY" else mt5.ORDER_TYPE_BUY,
        "position":      pos.ticket,
        "price":         close_price,
        "deviation":     20,
        "magic":         0,
        "comment":       getattr(pos, "comment", "") or "",  # คง comment เดิมของ position
        "type_time":     mt5.ORDER_TIME_GTC,
        "type_filling":  _get_filling_mode(),
    })
    ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
    ts = now_bkk().strftime('%H:%M:%S')
    if ok:
        print(f"[{ts}] TSO partial close ticket={pos.ticket} {pos_type} vol={send_vol} price={close_price:.2f} reason=[{reason}]")
    else:
        retcode = r.retcode if r is not None else "None"
        print(f"[{ts}] TSO partial close FAIL ticket={pos.ticket} retcode={retcode}")
    return ok


_entry_state = {}
_s6_state = {}
_s6i_state = {}
_s20_escape_state = {}  # Track max fibo level reached: {ticket: "RUN" or "3" or None}

# ==========================================
# 0) Helper Functions
async def check_s20_escape(app):
    """
    S20 Fibo Escape Trailing System (ระบบหนีตาย)
    พฤติกรรมความล้มเหลวตามคัมภีร์:
    - ถ้าราคาวิ่งไปถึง Fibo 3 หรือ RUN แล้วร่วงลงมาหาด่าน 1 หรือ 2 แต่ไม่สามารถยืน 2 ได้ (ทะลุ 2 ลงมา)
    - ราคาจะเกิดการเทขายอย่างหนักและร่วงทะลุจุด 0 ทันที
    """
    from trailing import position_zone_meta, _s20_escape_state, _close_position

    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        return

    for pos in positions:
        ticket = pos.ticket
        comment = pos.comment
        if "_S20_" not in comment:
            continue

        zmeta = position_zone_meta.get(ticket, {})
        if not zmeta or "fibo_2" not in zmeta:
            continue

        fibo_2 = zmeta.get("fibo_2")
        fibo_3 = zmeta.get("fibo_3")
        fibo_run = zmeta.get("fibo_run")
        if not fibo_2 or not fibo_3 or not fibo_run:
            continue

        pos_type = "BUY" if pos.type == 0 else "SELL"
        current_price = mt5.symbol_info_tick(pos.symbol).bid if pos_type == "BUY" else mt5.symbol_info_tick(pos.symbol).ask
        
        # 1. Update max level reached
        state = _s20_escape_state.get(ticket)
        if pos_type == "BUY":
            if current_price >= fibo_run:
                _s20_escape_state[ticket] = "RUN"
            elif current_price >= fibo_3 and _s20_escape_state.get(ticket) != "RUN":
                _s20_escape_state[ticket] = "3"
        else:
            if current_price <= fibo_run:
                _s20_escape_state[ticket] = "RUN"
            elif current_price <= fibo_3 and _s20_escape_state.get(ticket) != "RUN":
                _s20_escape_state[ticket] = "3"
                
        # 2. Check Escape Condition
        reached = _s20_escape_state.get(ticket)
        if not reached:
            continue
            
        # ถ้าไปถึงเป้าหมายสูงๆ แล้ว (3 หรือ RUN)
        # แล้วย่อลงมาทะลุ Fibo 2 (ยืน 2 ไม่ได้)
        # We need the last closed candle
        rates = mt5.copy_rates_from_pos(pos.symbol, mt5.TIMEFRAME_M1, 1, 1)
        if not rates or len(rates) == 0:
            continue
        last_close = rates[0]['close']
        
        is_break_2 = False
        if pos_type == "BUY":
            if last_close < fibo_2:
                is_break_2 = True
        else:
            if last_close > fibo_2:
                is_break_2 = True
                
        if is_break_2:
            reason = f"Fibo {reached} -> Break 2 (Escape)"
            if _close_position(pos, pos_type, f"S20 Escape ({reached} to Break 2)"):
                bot_log.log_trade("S20_ESCAPE", f"Ticket {ticket} Hit {reached} but broke Fibo 2! Escaping.")
                from notifications import notify_limit_fill
                await notify_limit_fill(app, pos, f"S20 Fibo Escape (Hit {reached}, Break 2)", "-", "-")
                if ticket in _s20_escape_state:
                    del _s20_escape_state[ticket]


async def check_scale_out_partial(app):
    """
    ทยอยปิด lot ตาม TSO levels (เสมอ 4 steps × 0.01 = 0.04 lot):
    ทั่วไป: [min(200,TP), min(300,TP), min(600,TP), TP] pt
    S10:    [min(200,TP), min(300,TP), TP/2, TP] pt
    เมื่อปิดครบ step จะลบ ticket ออกจาก scale_out_state
    """
    if not config.scale_out_state:
        return

    # timing breakdown — กัน MT5 call (โดยเฉพาะ order_send ใน _tso_close_partial) ค้างแบบไม่รู้ตัว
    _t0 = time.perf_counter()
    _query_dt = 0.0          # เวลา query positions/orders/tick ตอนต้น
    _close_dt = 0.0          # เวลารวมใน _tso_close_partial (order_send)
    _close_calls = 0         # จำนวนครั้งที่เรียก order_send

    positions = mt5.positions_get(symbol=SYMBOL) or []
    pos_by_ticket = {int(p.ticket): p for p in positions}
    pending_orders = mt5.orders_get(symbol=SYMBOL) or []
    pending_tickets = {int(o.ticket) for o in pending_orders}

    # cleanup: ลบ ticket ที่ไม่มีอยู่แล้ว (ปิดไปแล้ว)
    for tk in list(config.scale_out_state.keys()):
        if tk not in pos_by_ticket and tk not in pending_tickets:
            config.scale_out_state.pop(tk, None)

    tick = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        return
    bid = float(getattr(tick, "bid", 0.0))
    ask = float(getattr(tick, "ask", 0.0))
    _query_dt = time.perf_counter() - _t0

    for tk, st in list(config.scale_out_state.items()):
        # ข้ามถ้ายังเป็น pending (รอ fill)
        if tk not in pos_by_ticket:
            continue
        pos = pos_by_ticket[tk]
        direction = st.get("direction", "BUY")
        entry     = float(st.get("entry", pos.price_open))
        per_tp    = float(st.get("per_tp_volume", 0.01))
        distances = st.get("tp_distances", [])
        step      = int(st.get("step", 0))
        sid_str   = str(st.get("sid", "") or "")

        if step >= len(distances):
            continue

        # อัปเดต flag is_pending = False (เพราะถูก fill แล้ว)
        if st.get("is_pending"):
            st["is_pending"] = False
            # อัปเดต entry เป็น price_open จริงของ position (กรณี slippage)
            try:
                st["entry"] = float(pos.price_open)
                entry = st["entry"]
            except Exception:
                pass

        # ── คำนวณ TP เดิมของ order (สำหรับ cap rule) ───────────
        # ใช้ค่าจาก position.tp (ค่าจริงปัจจุบันใน MT5) เพื่อรองรับกรณีโดน trail/edit
        try:
            tp_orig = float(pos.tp or 0)
        except Exception:
            tp_orig = 0.0
        if tp_orig > 0:
            if direction == "BUY":
                tp_orig_dist = tp_orig - entry
            else:
                tp_orig_dist = entry - tp_orig
        else:
            tp_orig_dist = 0.0  # ไม่มี TP → ไม่ cap

        # คำนวณว่าราคาวิ่งผ่าน entry ไปแล้วเท่าไหร่
        cur_price = bid if direction == "BUY" else ask
        if direction == "BUY":
            passed = cur_price - entry
        else:
            passed = entry - cur_price

        if passed <= 0:
            continue

        # ── effective distance ต่อ step ────────────────────────
        # กฎทั่วไป: ถ้า TP เดิม < TSO_dist → ใช้ TP เดิม (cap)
        # S10 พิเศษ: ขั้นสุดท้าย (step == last) → ใช้ TP เดิมเสมอ (ถ้ามี)
        last_step_idx = len(distances) - 1

        def _effective_dist(i):
            tso_d = float(distances[i])
            if sid_str == "10" and i == last_step_idx and tp_orig_dist > 0:
                return tp_orig_dist                           # S10 TP3 = TP เดิม เสมอ
            if tp_orig_dist > 0 and tp_orig_dist < tso_d:
                return tp_orig_dist                           # cap by TP เดิม
            return tso_d

        # check ทีละขั้น (อาจปิดหลายขั้นในรอบเดียวถ้าราคากระโดด)
        while step < len(distances) and passed >= _effective_dist(step):
            tp_pts = config.SCALE_OUT_TP_POINTS[step] if step < len(config.SCALE_OUT_TP_POINTS) else 0
            eff_d = _effective_dist(step)
            tso_d = float(distances[step])
            # สร้าง reason ที่บอก cap ด้วย (debug-friendly)
            if eff_d < tso_d:
                reason = f"TSO TP{step+1} ({tp_pts}pt cap→{eff_d:.2f})"
            elif sid_str == "10" and step == last_step_idx and tp_orig_dist > 0:
                reason = f"TSO TP{step+1} (S10 TP_orig {eff_d:.2f})"
            else:
                reason = f"TSO TP{step+1} ({tp_pts}pt)"
            _cs0 = time.perf_counter()
            ok = _tso_close_partial(pos, direction, per_tp, reason)
            _close_dt += time.perf_counter() - _cs0
            _close_calls += 1
            if not ok:
                break
            step += 1
            st["step"] = step
            # ── log event TSO_PARTIAL_CLOSE_TP{step} ──
            try:
                log_event(
                    f"TSO_PARTIAL_CLOSE_TP{step}",
                    f"TP{step}/{len(distances)} | {reason}",
                    ticket=int(tk),
                    side=direction,
                    sid=sid_str,
                    step=step,
                    target_dist=round(eff_d, 2),
                    passed_dist=round(passed, 2),
                    close_volume=float(per_tp),
                    close_price=round(cur_price, 2),
                    entry=round(entry, 2),
                    remaining_steps=len(distances) - step,
                )
            except Exception:
                pass
            try:
                from notifications import tg_queue
                await tg(app,
                    f"📈 *Scale-Out TP{step}*\n"
                    f"━━━━━━━━━━━━━━━━━\n"
                    f"Ticket: `{tk}`\n"
                    f"{direction} | ปิด {per_tp} lot @ {cur_price:.2f}\n"
                    f"ระยะผ่าน entry: {passed:.2f} (target {eff_d:.2f})\n"
                    f"ขั้นที่เหลือ: {len(distances) - step}/{len(distances)}"
                )
            except Exception:
                pass
            # refresh position หลัง partial close
            new_pos = mt5.positions_get(ticket=tk)
            if not new_pos:
                # ปิดหมดแล้ว → ลบ state
                config.scale_out_state.pop(tk, None)
                break

        if step >= len(distances):
            # ปิดครบทุกขั้นแล้ว
            config.scale_out_state.pop(tk, None)

    # ── timing breakdown: log ถ้าใช้เวลานานผิดปกติ (> 3s) ──
    _total = time.perf_counter() - _t0
    if _total > 3.0:
        _other = _total - _query_dt - _close_dt
        log_event(
            "SCALE_OUT_SLOW",
            f"check_scale_out_partial ใช้เวลา {_total:.2f}s > 3s",
            breakdown=(f"query={_query_dt:.2f}s order_send={_close_dt:.2f}s"
                       f"({_close_calls} calls) other={_other:.2f}s"),
            tickets=len(config.scale_out_state),
        )


def scale_out_cleanup_on_disable() -> dict:
    """
    เรียกตอน toggle Scale-Out จาก ON → OFF:
    - Position ที่ลงทะเบียน TSO (non-S13): ปิดทั้งหมด
    - Pending ที่ลงทะเบียน TSO (non-S13): ยกเลิก + สร้างใหม่ด้วย lot เดิม (base_volume)
    - S13 orders: ไม่ถูกยุ่ง (ไม่อยู่ใน scale_out_state)
    Return summary dict
    """
    closed = 0
    reset_pending = 0
    errors = []

    if not config.scale_out_state:
        return {"closed": 0, "reset_pending": 0, "errors": []}

    positions = mt5.positions_get(symbol=SYMBOL) or []
    pos_by_ticket = {int(p.ticket): p for p in positions}
    pending_orders = mt5.orders_get(symbol=SYMBOL) or []
    pending_by_ticket = {int(o.ticket): o for o in pending_orders}

    for tk, st in list(config.scale_out_state.items()):
        direction = st.get("direction", "BUY")
        base_vol  = float(st.get("base_volume", 0.01))

        # ── 1) เป็น position ที่ fill แล้ว → ปิดทั้งหมด ──
        if tk in pos_by_ticket:
            pos = pos_by_ticket[tk]
            ok, _ = _close_position(pos, direction, "TSO disabled → close all")
            if ok:
                closed += 1
            else:
                errors.append(f"close pos {tk} fail")
            config.scale_out_state.pop(tk, None)
            continue

        # ── 2) เป็น pending → ยกเลิก + สร้างใหม่ด้วย base_volume ──
        if tk in pending_by_ticket:
            order = pending_by_ticket[tk]
            try:
                # ยกเลิกของเดิม
                cancel_r = mt5.order_send({
                    "action":  mt5.TRADE_ACTION_REMOVE,
                    "order":   tk,
                })
                cancel_ok = cancel_r is not None and cancel_r.retcode == mt5.TRADE_RETCODE_DONE
                if not cancel_ok:
                    rc = cancel_r.retcode if cancel_r else "None"
                    errors.append(f"cancel pending {tk} fail (retcode {rc})")
                    config.scale_out_state.pop(tk, None)
                    continue

                # สร้างใหม่ด้วย base_volume — ใช้ field เดิมทั้งหมด
                # ปิด SCALE_OUT_ENABLED ชั่วคราวเพื่อไม่ให้ตัวมัน scale ซ้ำ
                send = {
                    "action":       mt5.TRADE_ACTION_PENDING,
                    "symbol":       SYMBOL,
                    "volume":       base_vol,
                    "type":         order.type,
                    "price":        float(order.price_open),
                    "sl":           float(order.sl) if order.sl else 0.0,
                    "tp":           float(order.tp) if order.tp else 0.0,
                    "deviation":    20,
                    "magic":        int(order.magic or 234001),
                    "comment":      str(order.comment or ""),
                    "type_time":    mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_RETURN,
                }
                r2 = mt5.order_send(send)
                ok2 = r2 is not None and r2.retcode == mt5.TRADE_RETCODE_DONE
                if ok2:
                    reset_pending += 1
                    # อัปเดต pending_order_tf mapping ให้ ticket ใหม่ใช้ค่าเดิม
                    try:
                        old_info = pending_order_tf.pop(tk, None)
                        if old_info is not None:
                            pending_order_tf[int(r2.order)] = old_info
                        old_ptf = position_tf.pop(tk, None)
                        if old_ptf is not None:
                            position_tf[int(r2.order)] = old_ptf
                        old_psid = position_sid.pop(tk, None)
                        if old_psid is not None:
                            position_sid[int(r2.order)] = old_psid
                        old_ppat = position_pattern.pop(tk, None)
                        if old_ppat is not None:
                            position_pattern[int(r2.order)] = old_ppat
                    except Exception:
                        pass
                else:
                    rc = r2.retcode if r2 else "None"
                    errors.append(f"recreate pending {tk}→? fail (retcode {rc})")
            except Exception as e:
                errors.append(f"pending {tk} exc: {e}")
            config.scale_out_state.pop(tk, None)
            continue

        # ── 3) ticket หายไปแล้ว (ปิด/cancel ไปก่อนหน้า) ──
        config.scale_out_state.pop(tk, None)

    return {"closed": closed, "reset_pending": reset_pending, "errors": errors}


def _close_position(pos, pos_type, comment):
    """Close a position immediately and return (success, close_price)."""
    # MT5 comment limit (broker นี้): ทดสอบแล้ว 29 chars OK / 30+ FAIL
    # comment ยาวเกินทำให้ order_send คืน None + mt5_err=(-2,'Invalid "comment" argument')
    # ใช้ 28 เผื่อ safety margin
    comment = str(comment)[:28]
    tick = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        return False, 0.0
    bid = float(getattr(tick, "bid", 0.0))
    ask = float(getattr(tick, "ask", 0.0))
    spread = round(ask - bid, 2)
    close_price = bid if pos_type == "BUY" else ask
    caller = _get_sltp_caller()
    r = mt5.order_send({
        "action":        mt5.TRADE_ACTION_DEAL,
        "symbol":        SYMBOL,
        "volume":        pos.volume,
        "type":          mt5.ORDER_TYPE_SELL if pos_type == "BUY" else mt5.ORDER_TYPE_BUY,
        "position":      pos.ticket,
        "price":         close_price,
        "deviation":     20,
        "magic":         0,
        "comment":       comment,
        "type_time":     mt5.ORDER_TIME_GTC,
        "type_filling":  _get_filling_mode(),
    })
    # ── inner retry ตอน r=None: MT5 ไม่ตอบเลย ──────────────────────────────────
    # สาเหตุที่พบ: connection ขาดชั่วคราวช่วง volatility สูง (เช่น 08:12 BKK)
    # mt5.symbol_info_tick() ทำงานจาก cache → OK แต่ order_send ต้องส่ง server จริง → None
    # Strategy:
    #   1) reinitialize MT5 connection (กัน disconnect)
    #   2) ลอง 3 filling modes: RETURN → IOC → FOK (option C)
    #      เพราะ broker อาจปฏิเสธ mode ใด mode หนึ่งในช่วง volatility
    if r is None:
        import time as _t
        _t.sleep(0.3)
        # ── reinit connection ──
        try:
            mt5.initialize()
        except Exception:
            pass
        _tick2 = mt5.symbol_info_tick(SYMBOL)
        if _tick2:
            _cp2 = float(getattr(_tick2, "bid", 0.0)) if pos_type == "BUY" else float(getattr(_tick2, "ask", 0.0))
            _base_req = {
                "action":    mt5.TRADE_ACTION_DEAL,
                "symbol":    SYMBOL,
                "volume":    pos.volume,
                "type":      mt5.ORDER_TYPE_SELL if pos_type == "BUY" else mt5.ORDER_TYPE_BUY,
                "position":  pos.ticket,
                "price":     _cp2,
                "deviation": 50,
                "magic":     0,
                "comment":   comment,
                "type_time": mt5.ORDER_TIME_GTC,
            }
            # ลอง filling modes ตาม priority: RETURN → IOC → FOK
            _fill_modes = [
                mt5.ORDER_FILLING_RETURN,
                mt5.ORDER_FILLING_IOC,
                mt5.ORDER_FILLING_FOK,
            ]
            for _fm in _fill_modes:
                r = mt5.order_send({**_base_req, "type_filling": _fm})
                if r is not None:
                    break   # ได้ result แล้ว (สำเร็จหรือ error code) → ออก loop
                _t.sleep(0.1)   # brief pause ระหว่าง mode
            if r is not None and r.retcode == mt5.TRADE_RETCODE_DONE:
                close_price = _cp2

    success = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
    if success:
        print(f"[{now_bkk().strftime('%H:%M:%S')}] CLOSE_DEBUG ok {pos_type} ticket={pos.ticket} close={close_price:.2f} bid={bid:.2f} ask={ask:.2f} spread={spread:.2f} entry={float(pos.price_open):.2f} reason=[{comment}]")
        print(f"[{now_bkk().strftime('%H:%M:%S')}] CLOSE {pos_type} ticket={pos.ticket} price={close_price:.2f} reason=[{comment}]")
        log_event("POSITION_CLOSE_REQUEST", comment, ticket=pos.ticket, side=pos_type, close_price=close_price, entry=pos.price_open, bid=bid, ask=ask, spread=spread, ok=True)
    else:
        retcode = r.retcode if r is not None else "None"
        # ถ้า order_send คืน None → ดึง mt5.last_error() เพื่อรู้สาเหตุ (เดิมไม่มี → ไม่รู้ว่า MT5 ปฏิเสธเพราะอะไร)
        mt5_err = mt5.last_error() if r is None else None
        mt5_err_str = f"{mt5_err}" if mt5_err and mt5_err[0] != 1 else None
        print(f"[{now_bkk().strftime('%H:%M:%S')}] CLOSE_DEBUG fail {pos_type} ticket={pos.ticket} bid={bid:.2f} ask={ask:.2f} spread={spread:.2f} entry={float(pos.price_open):.2f} retcode={retcode}{' mt5err='+mt5_err_str if mt5_err_str else ''} reason=[{comment}]")
        print(f"[{now_bkk().strftime('%H:%M:%S')}] CLOSE FAIL {pos_type} ticket={pos.ticket} retcode={retcode} reason=[{comment}]")
        log_event("POSITION_CLOSE_REQUEST", comment, ticket=pos.ticket, side=pos_type, entry=pos.price_open, bid=bid, ask=ask, spread=spread, ok=False, retcode=retcode, mt5_err=mt5_err_str)
    return success, close_price


def _build_s1_forward_meta(signal: str, detect_bar_time: int, forward_bars: int = 5) -> dict:
    return {
        "enabled": True,
        "signal": str(signal or "").upper(),
        "detect_bar_time": int(detect_bar_time or 0),
        "forward_bars": max(1, int(forward_bars or 5)),
        "confirmed": False,
        "confirmed_sid": 0,
        "confirmed_bar_time": 0,
    }


async def _close_linked_s11_for_tf(app, tf_name: str, trigger_reason: str) -> None:
    if not tf_name:
        return

    orders = mt5.orders_get(symbol=SYMBOL) or []
    positions = mt5.positions_get(symbol=SYMBOL) or []
    canceled_orders = []
    closed_positions = []

    for order in orders:
        ticket = int(order.ticket)
        if int(position_sid.get(ticket, 0) or 0) != 11:
            continue
        if str(position_tf.get(ticket, "")) != str(tf_name):
            continue
        r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": ticket})
        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
            info = pending_order_tf.pop(ticket, None)
            position_tf.pop(ticket, None)
            position_sid.pop(ticket, None)
            position_pattern.pop(ticket, None)
            position_trend_filter.pop(ticket, None)
            position_zone_meta.pop(ticket, None)
            position_forward_meta.pop(ticket, None)
            canceled_orders.append(ticket)
            log_event(
                "ORDER_CANCELED",
                f"S11 canceled because {trigger_reason}",
                ticket=ticket,
                tf=tf_name,
                sid=11,
                signal=(info or {}).get("signal", "") if isinstance(info, dict) else "",
                entry=(info or {}).get("entry") if isinstance(info, dict) else None,
                sl=(info or {}).get("sl") if isinstance(info, dict) else None,
                tp=(info or {}).get("tp") if isinstance(info, dict) else None,
            )

    for pos in positions:
        ticket = int(pos.ticket)
        if int(position_sid.get(ticket, 0) or 0) != 11:
            continue
        if str(position_tf.get(ticket, "")) != str(tf_name):
            continue
        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        ok_close, close_price = _close_position(pos, pos_type, f"s11 linked close [{tf_name}]")
        if ok_close:
            position_tf.pop(ticket, None)
            position_sid.pop(ticket, None)
            position_pattern.pop(ticket, None)
            position_trend_filter.pop(ticket, None)
            position_zone_meta.pop(ticket, None)
            position_forward_meta.pop(ticket, None)
            closed_positions.append((ticket, close_price, pos_type))

    if canceled_orders or closed_positions:
        s11_reset_state(tf_name)
        lines = [f"🧹 *S11 linked cleanup* [{tf_name}]"]
        if canceled_orders:
            lines.append(f"🗑️ Pending S11: `{', '.join(map(str, canceled_orders))}`")
        if closed_positions:
            lines.append(
                "🔒 Position S11: " + ", ".join(
                    f"`{ticket}` {side} @{close_price:.2f}" for ticket, close_price, side in closed_positions
                )
            )
        lines.append(f"เหตุผล: {trigger_reason}")
        await tg(app, "\n".join(lines))


def _evaluate_s1_forward_confirm(rates, signal: str, detect_bar_time: int, tf_secs: int, forward_bars: int) -> dict:
    signal = str(signal or "").upper()
    detect_bar_time = int(detect_bar_time or 0)
    tf_secs = int(tf_secs or 0)
    forward_bars = max(1, int(forward_bars or 5))
    if rates is None or len(rates) < 4 or detect_bar_time <= 0 or tf_secs <= 0:
        return {
            "confirmed": False,
            "expired": False,
            "last_closed_time": int(rates[-1]["time"]) if rates is not None and len(rates) else 0,
            "checked_bars": 0,
            "matched_sid": 0,
            "matched_bar_time": 0,
        }

    deadline_time = detect_bar_time + (tf_secs * forward_bars)
    last_closed_time = int(rates[-1]["time"])
    matched_sid = 0
    matched_bar_time = 0
    checked_bars = 0

    for idx in range(len(rates)):
        bar_time = int(rates[idx]["time"])
        if bar_time <= detect_bar_time:
            continue
        if bar_time > deadline_time:
            break
        if idx < 2:
            continue
        checked_bars += 1
        sliced_rates = rates[: idx + 1]

        try:
            s2 = strategy_2(sliced_rates)
        except Exception:
            s2 = {}
        if str(s2.get("signal", "")).upper() == "FVG_DETECTED":
            fvg = s2.get("fvg") or {}
            if str(fvg.get("signal", "")).upper() == signal:
                matched_sid = 2
                matched_bar_time = bar_time
                break

        try:
            s3 = strategy_3(sliced_rates)
        except Exception:
            s3 = {}
        if str(s3.get("signal", "")).upper() == signal:
            matched_sid = 3
            matched_bar_time = bar_time
            break

    return {
        "confirmed": matched_sid in (2, 3),
        "expired": last_closed_time >= deadline_time,
        "last_closed_time": last_closed_time,
        "checked_bars": checked_bars,
        "matched_sid": matched_sid,
        "matched_bar_time": matched_bar_time,
        "deadline_time": deadline_time,
    }


async def check_s1_zone_rules(app):
    _mode = getattr(config, "S1_ZONE_MODE", "")
    if _mode not in ("zone", "swing"):
        return

    from strategy1 import evaluate_s1_zone_status
    from datetime import datetime, timezone, timedelta
    BKK = timezone(timedelta(hours=7))

    now = now_bkk().strftime("%H:%M:%S")
    orders = mt5.orders_get(symbol=SYMBOL) or []
    positions = mt5.positions_get(symbol=SYMBOL) or []
    open_order_tickets = {int(o.ticket) for o in orders}
    open_pos_tickets = {int(p.ticket) for p in positions}

    for t in list(position_zone_meta.keys()):
        if t not in open_order_tickets and t not in open_pos_tickets:
            position_zone_meta.pop(t, None)

    # Pending S1: check zone or swing rule
    for order in orders:
        ticket = int(order.ticket)
        info = pending_order_tf.get(ticket)
        if not isinstance(info, dict) or int(info.get("sid", 0) or 0) != 1:
            continue
        zone_meta = info.get("s1_zone_meta") or {}
        if not zone_meta.get("enabled"):
            continue

        tf = info.get("tf") or position_tf.get(ticket)
        if not tf:
            continue
        tf_val = TF_OPTIONS.get(tf, mt5.TIMEFRAME_M1)
        lookback = TF_LOOKBACK.get(tf, SWING_LOOKBACK)
        rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, lookback + 6)
        if rates is None or len(rates) < 5:
            continue

        if _mode == "zone":
            # รอ 7 แท่งหลัง detect ก่อน — zone อาจยังไม่ก่อตัว
            _fwd_meta = info.get("s1_forward_meta") or {}
            _detect_bar_time = int(_fwd_meta.get("detect_bar_time", 0) or 0)
            if _detect_bar_time > 0:
                _candles_passed = sum(1 for r in rates if int(r["time"]) > _detect_bar_time)
                if _candles_passed < 7:
                    continue  # ยังไม่ถึง 7 แท่ง ข้ามไปก่อน

            zone_state = evaluate_s1_zone_status(
                rates,
                str(zone_meta.get("signal") or info.get("signal") or ""),
                float(zone_meta.get("zone_price", 0.0) or 0.0),
                tf=tf,
            )
            if zone_state.get("in_zone", True):
                continue

            zone_side = "Low Zone" if str(zone_meta.get("signal") or info.get("signal") or "") == "BUY" else "High Zone"
            reason = (
                f"S1 Zone Cancel [{tf}]: pending still outside {zone_side} | "
                f"zone_price:{float(zone_state.get('zone_price', 0.0)):.2f} | "
                f"boundary:{float(zone_state.get('boundary_price', 0.0)):.2f} | "
                f"swing:{float(zone_state.get('swing_price', 0.0)):.2f}"
            )
        else: # _mode == "swing"
            _fwd_meta = info.get("s1_forward_meta") or {}
            t_detect = int(_fwd_meta.get("detect_bar_time", 0) or 0)
            if t_detect <= 0:
                continue

            t_last_closed = int(rates[-1]["time"])
            tf_secs = TF_SECONDS_MAP.get(tf, 60)

            import hhll_swing
            hhll_swing.fetch_hhll(tf)
            d = hhll_swing.get_hhll_data(tf) or {}

            sig = str(zone_meta.get("signal") or info.get("signal") or "").upper()
            pts = []
            if sig == "BUY":
                hl = d.get("hl")
                ll = d.get("ll")
                pts = [p for p in (hl, ll) if p and p.get("time")]
            elif sig == "SELL":
                hh = d.get("hh")
                lh = d.get("lh")
                pts = [p for p in (hh, lh) if p and p.get("time")]

            hhll_right = int(getattr(config, "HHLL_RIGHT", 5) or 5)
            pattern_candle_times = {t_detect, t_detect - tf_secs, t_detect - 2 * tf_secs, t_detect - 3 * tf_secs}
            has_valid_swing = False
            for pt in pts:
                t_swing = int(pt["time"])
                if t_swing in pattern_candle_times:
                    t_confirm = t_swing + hhll_right * tf_secs
                    if t_detect <= t_confirm <= t_detect + 5 * tf_secs:
                        has_valid_swing = True
                        break

            if has_valid_swing:
                continue

            if t_last_closed > t_detect + 4 * tf_secs:
                detect_str = datetime.fromtimestamp(t_detect, tz=BKK).strftime("%H:%M")
                deadline_str = datetime.fromtimestamp(t_detect + 4 * tf_secs, tz=BKK).strftime("%H:%M")
                reason = f"S1 Swing Cancel [{tf}]: no swing {sig} confirmed in 4 bars | detect:{detect_str} | deadline:{deadline_str}"
            else:
                continue

        r = mt5.order_send({
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": ticket,
        })
        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
            pending_order_tf.pop(ticket, None)
            sig = str(zone_meta.get("signal") or info.get("signal") or "")
            side_icon = "🟢" if sig == "BUY" else "🔴"
            log_event(
                "ORDER_CANCELED",
                reason,
                ticket=ticket,
                tf=tf,
                side=sig,
                sid=1,
                order_type=_pending_order_type_name(order),
                entry=info.get("entry"),
                sl=info.get("sl"),
                tp=info.get("tp"),
                flow_id=info.get("flow_id", ""),
            )
            await tg(app, (
                f"🗑️ *S1 {'Swing' if _mode == 'swing' else 'Zone'} Cancel*\n"
                f"{side_icon} [{tf}] Ticket:`{ticket}`\n"
                f"Entry:`{float(info.get('entry', 0.0)):.2f}`\n"
                f"เหตุผล: {reason}"
            ))
            print(f"🗑️ [{now}] S1 {_mode} cancel {ticket} [{tf}]: {reason}")

    # Filled S1: if outside zone/swing rule -> close.
    for pos in positions:
        ticket = int(pos.ticket)
        if position_sid.get(ticket) != 1:
            continue
        zone_meta = position_zone_meta.get(ticket) or {}
        if not zone_meta.get("enabled"):
            continue

        tf = position_tf.get(ticket)
        if not tf:
            continue
        tf_val = TF_OPTIONS.get(tf, mt5.TIMEFRAME_M1)
        lookback = TF_LOOKBACK.get(tf, SWING_LOOKBACK)
        rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, lookback + 6)
        if rates is None or len(rates) < 5:
            continue

        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"

        if _mode == "zone":
            zone_state = evaluate_s1_zone_status(
                rates,
                str(zone_meta.get("signal") or pos_type or ""),
                float(zone_meta.get("zone_price", 0.0) or 0.0),
                tf=tf,
            )
            if zone_state.get("in_zone", True) or float(pos.profit) >= 0.0:
                continue

            zone_side = "Low Zone" if pos_type == "BUY" else "High Zone"
            reason = (
                f"S1 Zone Loss Exit [{tf}]: outside {zone_side} with loss | "
                f"profit:{float(pos.profit):.2f} | "
                f"zone_price:{float(zone_state.get('zone_price', 0.0)):.2f} | "
                f"boundary:{float(zone_state.get('boundary_price', 0.0)):.2f} | "
                f"swing:{float(zone_state.get('swing_price', 0.0)):.2f}"
            )
        else: # _mode == "swing"
            forward_meta = position_forward_meta.get(ticket) or {}
            t_detect = int(forward_meta.get("detect_bar_time", 0) or 0)
            if t_detect <= 0 or forward_meta.get("confirmed"):
                continue

            t_last_closed = int(rates[-1]["time"])
            tf_secs = TF_SECONDS_MAP.get(tf, 60)

            import hhll_swing
            hhll_swing.fetch_hhll(tf)
            d = hhll_swing.get_hhll_data(tf) or {}

            pts = []
            if pos_type == "BUY":
                hl = d.get("hl")
                ll = d.get("ll")
                pts = [p for p in (hl, ll) if p and p.get("time")]
            elif pos_type == "SELL":
                hh = d.get("hh")
                lh = d.get("lh")
                pts = [p for p in (hh, lh) if p and p.get("time")]

            hhll_right = int(getattr(config, "HHLL_RIGHT", 5) or 5)
            pattern_candle_times = {t_detect, t_detect - tf_secs, t_detect - 2 * tf_secs}
            has_valid_swing = False
            for pt in pts:
                t_swing = int(pt["time"])
                if t_swing in pattern_candle_times:
                    t_confirm = t_swing + hhll_right * tf_secs
                    if t_detect <= t_confirm <= t_detect + 5 * tf_secs:
                        has_valid_swing = True
                        break

            if has_valid_swing:
                forward_meta["confirmed"] = True
                position_forward_meta[ticket] = forward_meta
                save_runtime_state()
                continue

            if t_last_closed > t_detect + 4 * tf_secs:
                detect_str = datetime.fromtimestamp(t_detect, tz=BKK).strftime("%H:%M")
                deadline_str = datetime.fromtimestamp(t_detect + 4 * tf_secs, tz=BKK).strftime("%H:%M")
                reason = f"S1 Swing Exit [{tf}]: no swing {pos_type} confirmed in 4 bars | detect:{detect_str} | deadline:{deadline_str}"
            else:
                continue

        ok_close, close_price = _close_position(pos, pos_type, f"s1 {_mode} exit [{tf}]")
        if ok_close:
            sig_e = "🟢" if pos_type == "BUY" else "🔴"
            await tg(app, (
                f"⚠️ *S1 {'Swing' if _mode == 'swing' else 'Zone'} Exit*\n"
                f"{sig_e} Ticket:`{ticket}` [{pos_type}] [{tf}]\n"
                f"Profit:`{float(pos.profit):.2f}`\n"
                f"ปิดที่:`{close_price:.2f}`\n"
                f"เหตุผล: {reason}"
            ))
            print(f"⚠️ [{now}] S1 {_mode} exit {ticket} [{tf}] close={close_price:.2f} | {reason}")
            await _close_linked_s11_for_tf(app, tf, f"S1 closed by {_mode} exit [{tf}]")


async def check_s1_forward_confirm_rules(app):
    now = now_bkk().strftime("%H:%M:%S")
    orders = mt5.orders_get(symbol=SYMBOL) or []
    positions = mt5.positions_get(symbol=SYMBOL) or []
    open_order_tickets = {int(o.ticket) for o in orders}
    open_pos_tickets = {int(p.ticket) for p in positions}

    for t in list(position_forward_meta.keys()):
        if t not in open_order_tickets and t not in open_pos_tickets:
            position_forward_meta.pop(t, None)

    for order in orders:
        ticket = int(order.ticket)
        info = pending_order_tf.get(ticket)
        if not isinstance(info, dict) or int(info.get("sid", 0) or 0) != 1:
            continue
        forward_meta = info.get("s1_forward_meta") or {}
        if not forward_meta.get("enabled") or forward_meta.get("confirmed"):
            continue

        tf = info.get("tf") or position_tf.get(ticket)
        if not tf:
            continue
        tf_val = TF_OPTIONS.get(tf, mt5.TIMEFRAME_M1)
        forward_bars = int(forward_meta.get("forward_bars", 5) or 5)
        lookback = max(TF_LOOKBACK.get(tf, SWING_LOOKBACK), forward_bars + 8)
        rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, lookback + 10)
        if rates is None or len(rates) < 5:
            continue

        state = _evaluate_s1_forward_confirm(
            rates,
            str(forward_meta.get("signal") or info.get("signal") or ""),
            int(forward_meta.get("detect_bar_time", 0) or 0),
            int(TF_SECONDS_MAP.get(tf, 0) or 0),
            forward_bars,
        )
        if state.get("confirmed"):
            forward_meta["confirmed"] = True
            forward_meta["confirmed_sid"] = int(state.get("matched_sid", 0) or 0)
            forward_meta["confirmed_bar_time"] = int(state.get("matched_bar_time", 0) or 0)
            info["s1_forward_meta"] = forward_meta
            continue
        if not state.get("expired"):
            continue

        r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": ticket})
        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
            pending_order_tf.pop(ticket, None)
            position_forward_meta.pop(ticket, None)
            sig = str(forward_meta.get("signal") or info.get("signal") or "")
            side_icon = "🟢" if sig == "BUY" else "🔴"
            reason = f"S1 Forward Cancel [{tf}]: ไม่เจอ S2/S3 ฝั่งเดียวกันใน {forward_bars} แท่งข้างหน้า"
            log_event(
                "ORDER_CANCELED",
                reason,
                ticket=ticket,
                tf=tf,
                side=sig,
                sid=1,
                order_type=_pending_order_type_name(order),
                entry=info.get("entry"),
                sl=info.get("sl"),
                tp=info.get("tp"),
                flow_id=info.get("flow_id", ""),
            )
            await tg(app, (
                f"🗑️ *S1 Forward Cancel*\n"
                f"{side_icon} [{tf}] Ticket:`{ticket}`\n"
                f"Entry:`{float(info.get('entry', 0.0)):.2f}`\n"
                f"เหตุผล: {reason}"
            ))
            print(f"🗑️ [{now}] S1 forward cancel {ticket} [{tf}]: {reason}")

    for pos in positions:
        ticket = int(pos.ticket)
        if position_sid.get(ticket) != 1:
            continue
        forward_meta = position_forward_meta.get(ticket) or {}
        if not forward_meta.get("enabled") or forward_meta.get("confirmed"):
            continue

        tf = position_tf.get(ticket)
        if not tf:
            continue
        tf_val = TF_OPTIONS.get(tf, mt5.TIMEFRAME_M1)
        forward_bars = int(forward_meta.get("forward_bars", 5) or 5)
        lookback = max(TF_LOOKBACK.get(tf, SWING_LOOKBACK), forward_bars + 8)
        rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, lookback + 10)
        if rates is None or len(rates) < 5:
            continue

        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        state = _evaluate_s1_forward_confirm(
            rates,
            str(forward_meta.get("signal") or pos_type or ""),
            int(forward_meta.get("detect_bar_time", 0) or 0),
            int(TF_SECONDS_MAP.get(tf, 0) or 0),
            forward_bars,
        )
        if state.get("confirmed"):
            forward_meta["confirmed"] = True
            forward_meta["confirmed_sid"] = int(state.get("matched_sid", 0) or 0)
            forward_meta["confirmed_bar_time"] = int(state.get("matched_bar_time", 0) or 0)
            position_forward_meta[ticket] = forward_meta
            continue
        if not state.get("expired"):
            continue

        reason = f"S1 Forward Exit [{tf}]: ไม่เจอ S2/S3 ฝั่งเดียวกันใน {forward_bars} แท่งข้างหน้า"
        ok_close, close_price = _close_position(pos, pos_type, f"s1 forward exit [{tf}]")
        if ok_close:
            position_forward_meta.pop(ticket, None)
            side_icon = "🟢" if pos_type == "BUY" else "🔴"
            await tg(app, (
                f"🔒 *S1 Forward Exit*\n"
                f"{side_icon} [{tf}] Ticket:`{ticket}`\n"
                f"ปิดที่:`{close_price:.2f}`\n"
                f"เหตุผล: {reason}"
            ))
            print(f"🔒 [{now}] S1 forward exit {ticket} [{tf}] close={close_price:.2f} | {reason}")
            await _close_linked_s11_for_tf(app, tf, f"S1 closed by forward confirm miss [{tf}]")


async def _cancel_s10_sibling_orders(app, filled_ticket: int, filled_info: dict, source_ticket: int | None = None) -> None:
    if not isinstance(filled_info, dict):
        return
    if int(filled_info.get("sid", 0) or 0) != 10:
        return
    sibling_tickets = [int(t) for t in (filled_info.get("s10_sibling_tickets") or []) if int(t) > 0]
    if not sibling_tickets:
        return

    open_orders = {int(o.ticket): o for o in (mt5.orders_get(symbol=SYMBOL) or [])}
    canceled = []
    for sibling_ticket in sibling_tickets:
        if source_ticket and sibling_ticket == int(source_ticket):
            continue
        if sibling_ticket not in open_orders:
            pending_order_tf.pop(sibling_ticket, None)
            continue
        r = mt5.order_send({
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": sibling_ticket,
        })
        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
            canceled.append(sibling_ticket)
            pending_order_tf.pop(sibling_ticket, None)
            log_event(
                "S10_SIBLING_CANCEL",
                "filled_other_model",
                ticket=sibling_ticket,
                filled_ticket=filled_ticket,
                tf=filled_info.get("tf", ""),
                signal=filled_info.get("signal", ""),
                group_id=filled_info.get("s10_group_id", ""),
            )

    if canceled:
        save_runtime_state()
        model_label = filled_info.get("s10_model", "?")
        await tg(app, (
            f"🧹 *S10 Cancel Sibling Pending*\n"
            f"Ticket Fill:`{filled_ticket}` Model:`{model_label}`\n"
            f"Cancel: `{', '.join(str(t) for t in canceled)}`"
        ))


def _get_sltp_caller():
    """Find the actual caller that requested an SL/TP change."""
    skip = {"_modify_sl", "_modify_sl_tp", "_apply_entry_sl_tp", "_get_sltp_caller", "_log_sltp_change"}
    for frame in inspect.stack()[1:]:
        if frame.function not in skip:
            return f"{frame.function}:{frame.lineno}"
    return "unknown"


def _trade_debug_enabled() -> bool:
    return bool(getattr(config, "TRADE_DEBUG", False))


def _log_sltp_change(mode, caller, pos, new_sl, new_tp, ok, result):
    """Forensic audit log for tracing who changed SL/TP."""
    if not getattr(config, "SLTP_AUDIT_DEBUG", False):
        return
    tick = mt5.symbol_info_tick(SYMBOL)
    bid = float(getattr(tick, "bid", 0.0)) if tick else 0.0
    ask = float(getattr(tick, "ask", 0.0)) if tick else 0.0
    spread = round(ask - bid, 2) if tick else 0.0
    retcode = getattr(result, "retcode", None) if result is not None else None
    comment = getattr(result, "comment", "") if result is not None else ""
    key = _sltp_dedup_key(f"{mode}:{caller}", pos, float(pos.sl), float(pos.tp), float(new_sl), float(new_tp), ok)
    if key != _last_sltp_cmd_key:
        print(
            f"[{now_bkk().strftime('%H:%M:%S')}] SLTP_TRACE mode={mode} caller={caller} "
            f"ticket={pos.ticket} type={'BUY' if pos.type == mt5.ORDER_TYPE_BUY else 'SELL'} "
            f"old_sl={float(pos.sl):.2f} old_tp={float(pos.tp):.2f} "
            f"new_sl={float(new_sl):.2f} new_tp={float(new_tp):.2f} "
            f"entry={float(pos.price_open):.2f} bid={bid:.2f} ask={ask:.2f} spread={spread:.2f} "
            f"ok={ok} retcode={retcode} comment={comment}"
        )
    _audit_sltp_event(f"{mode}:{caller}", pos, float(pos.sl), float(pos.tp), float(new_sl), float(new_tp), ok, result)


def _modify_sl(pos, new_sl):
    caller = _get_sltp_caller()
    """Modify SL for an open position."""
    r = mt5.order_send({
        "action":   mt5.TRADE_ACTION_SLTP,
        "symbol":   SYMBOL,
        "position": pos.ticket,
        "sl":       new_sl,
        "tp":       pos.tp,
    })
    ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
    _log_sltp_change("SL_ONLY", caller, pos, new_sl, pos.tp, ok, r)
    if not ok:
        retcode = r.retcode if r else "None"
        comment = r.comment if r else ""
        print(f"⚠️ _modify_sl FAIL ticket={pos.ticket} SL={new_sl} retcode={retcode} comment={comment}")
    return ok


def _modify_sl_tp(pos, new_sl, new_tp):
    caller = _get_sltp_caller()
    """Modify SL and TP for an open position together."""
    r = mt5.order_send({
        "action":   mt5.TRADE_ACTION_SLTP,
        "symbol":   SYMBOL,
        "position": pos.ticket,
        "sl":       new_sl,
        "tp":       new_tp,
    })
    ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
    _log_sltp_change("SL_TP", caller, pos, new_sl, new_tp, ok, r)
    if not ok:
        retcode = r.retcode if r else "None"
        comment = r.comment if r else ""
        print(f"⚠️ _modify_sl_tp FAIL ticket={pos.ticket} SL={new_sl} TP={new_tp} retcode={retcode} comment={comment}")
    return ok


def _modify_pending_sl(order, new_sl):
    """Modify SL for a pending order."""
    r = mt5.order_send({
        "action": mt5.TRADE_ACTION_MODIFY,
        "order": order.ticket,
        "symbol": order.symbol,
        "price": order.price_open,
        "sl": new_sl,
        "tp": order.tp,
        "type_time": order.type_time,
        "type_filling": order.type_filling,
    })
    ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
    return ok, r


def _modify_pending_entry(order, new_price: float):
    """Modify entry price of a pending limit order."""
    r = mt5.order_send({
        "action":       mt5.TRADE_ACTION_MODIFY,
        "order":        order.ticket,
        "symbol":       order.symbol,
        "price":        round(new_price, 2),
        "sl":           float(order.sl) if order.sl else 0.0,
        "tp":           float(order.tp) if order.tp else 0.0,
        "type_time":    order.type_time,
        "type_filling": order.type_filling,
    })
    ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
    return ok, r


def _apply_entry_sl_tp(pos, new_sl, new_tp):
    """Apply entry SL/TP update based on config; default updates only SL."""
    if getattr(config, "ENTRY_CANDLE_UPDATE_TP", False):
        return _modify_sl_tp(pos, new_sl, new_tp)
    return _modify_sl(pos, new_sl)


def _price_differs(a: float, b: float, tol: float = 0.01) -> bool:
    return abs(float(a) - float(b)) > tol


def _bar_close(bar) -> float:
    return float(bar["close"])


def _bar_open(bar) -> float:
    return float(bar["open"])


def _bar_high(bar) -> float:
    return float(bar["high"])


def _bar_low(bar) -> float:
    return float(bar["low"])


def _is_green_engulf_break(cur_bar, prev_bar, level: float) -> bool:
    return (
        _bar_close(cur_bar) > _bar_open(cur_bar)
        and _bar_close(prev_bar) > _bar_open(prev_bar)
        and _bar_close(cur_bar) > float(level)
        and _bar_close(cur_bar) > _bar_high(prev_bar)
    )


def _is_red_engulf_break(cur_bar, prev_bar, level: float) -> bool:
    return (
        _bar_close(cur_bar) < _bar_open(cur_bar)
        and _bar_close(prev_bar) < _bar_open(prev_bar)
        and _bar_close(cur_bar) < float(level)
        and _bar_close(cur_bar) < _bar_low(prev_bar)
    )


def _get_closed_bar(pos, tf_val=None):
    """
    Get the correct closed bars for the current entry state.

    Returns `(entry_bar, next_bar)` where:
    - `entry_bar` is the candle where the fill actually happened
    - `next_bar` is the fully closed candle after `entry_bar`

    Uses `start=1` to skip the live candle `[0]`, so `rates[-1]`
    is always the latest fully closed candle.

    Timing example on M1:
      13:22:xx fill -> wait for candle 13:22 to close
      13:23:xx -> entry_bar=13:22, next_bar=None, can evaluate entry candle
      13:24:xx -> entry_bar=13:22, next_bar=13:23, can evaluate waiting_next / waiting_bad
    """
    if tf_val is None:
        tf_val = mt5.TIMEFRAME_M1
    # start=1: skip the live candle [0], so rates[-1] is always the latest closed candle
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, 20)
    if rates is None or len(rates) < 2:
        return None, None

    fill_time = int(pos.time)

    tf_seconds = _get_tf_seconds(tf_val)

    # rates[-1] is the latest fully closed candle
    # entry_bar is valid once fill_time is earlier than that candle close time
    latest_closed_open = int(rates[-1]["time"])
    latest_closed_close = latest_closed_open + tf_seconds
    if fill_time >= latest_closed_close:
        return None, None

    # Find entry_bar and next_bar
    entry_bar = None
    next_bar  = None
    for i, bar in enumerate(rates):
        bar_open = int(bar["time"])
        if bar_open <= fill_time:
            if i + 1 < len(rates) and int(rates[i+1]["time"]) > fill_time:
                entry_bar = bar
                next_bar  = rates[i+1]
                break
            elif i + 1 >= len(rates):
                entry_bar = bar
                break

    return entry_bar, next_bar


def _get_tf_seconds(tf_val):
    tf_seconds_map = {
        mt5.TIMEFRAME_M1: 60,
        mt5.TIMEFRAME_M5: 300,
        mt5.TIMEFRAME_M15: 900,
        mt5.TIMEFRAME_M30: 1800,
        mt5.TIMEFRAME_H1: 3600,
        mt5.TIMEFRAME_H4: 14400,
        mt5.TIMEFRAME_H12: 43200,
        mt5.TIMEFRAME_D1: 86400,
    }
    return tf_seconds_map.get(tf_val, 60)


def _get_current_price(pos_type):
    """Get the current decision-side price for a position."""
    tick = mt5.symbol_info_tick(SYMBOL)
    if tick:
        return float(tick.bid if pos_type == "BUY" else tick.ask)
    return 0.0


def _focus_side_presence(positions, pending_orders):
    """Return `(has_buy, has_sell)` including positions and pending limit/stop orders."""
    has_buy = any(p.type == mt5.ORDER_TYPE_BUY for p in positions) or any(
        o.type in (mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP)
        for o in pending_orders
    )
    has_sell = any(p.type == mt5.ORDER_TYPE_SELL for p in positions) or any(
        o.type in (mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP)
        for o in pending_orders
    )
    return has_buy, has_sell


def _focus_update_frozen_side(feature: str, positions, pending_orders):
    """
    Update the marker for a feature (`trail_sl` or `entry_candle`) based on current state:
    - if no buy/sell orders remain, reset marker to None
    - if marker is None and only one side exists, freeze to that side
    - if marker is None and both sides exist, wait until one side disappears first
    - if marker already exists, keep it

    Returns the marker after update.
    """
    current = _focus_frozen_side.get(feature)
    has_buy, has_sell = _focus_side_presence(positions, pending_orders)

    if not has_buy and not has_sell:
        if current is not None:
            _focus_frozen_side[feature] = None
            try:
                save_runtime_state()
            except Exception:
                pass
        return None

    if current is None:
        new_side = None
        if has_buy and not has_sell:
            new_side = "BUY"
        elif has_sell and not has_buy:
            new_side = "SELL"
        if new_side is not None:
            _focus_frozen_side[feature] = new_side
            try:
                save_runtime_state()
            except Exception:
                pass
        return new_side

    return current


def _focus_gate_passed(feature: str, frozen_side: str, positions, ref_tf) -> bool:
    """
    Check whether the frozen side has a position with profit above threshold.
    If yes, the opposite side is allowed to continue its trail/ECM logic normally.

    `feature` is `trail_sl` or `entry_candle` and uses its own config group.
    """
    if feature == "trail_sl":
        points = int(getattr(config, "TRAIL_SL_FOCUS_NEW_POINTS", 100))
        tf_mode = getattr(config, "TRAIL_SL_FOCUS_NEW_TF_MODE", "separate")
    else:
        points = int(getattr(config, "ENTRY_CANDLE_FOCUS_NEW_POINTS", 100))
        tf_mode = getattr(config, "ENTRY_CANDLE_FOCUS_NEW_TF_MODE", "separate")
    points = points * config.points_scale()   # BTC uses 4x point scaling relative to XAU base

    tick = mt5.symbol_info_tick(SYMBOL)
    info = mt5.symbol_info(SYMBOL)
    if not tick or not info:
        return False

    pt = float(info.point) if info.point else 0.01
    threshold = points * pt + _get_spread_price()
    bid_cur = float(tick.bid)
    ask_cur = float(tick.ask)

    if frozen_side == "BUY":
        for p in positions:
            if p.type != mt5.ORDER_TYPE_BUY:
                continue
            if (bid_cur - float(p.price_open)) > threshold:
                if tf_mode == "combined" or position_tf.get(p.ticket) == ref_tf:
                    return True
        return False

    for p in positions:
        if p.type != mt5.ORDER_TYPE_SELL:
            continue
        if (float(p.price_open) - ask_cur) > threshold:
            if tf_mode == "combined" or position_tf.get(p.ticket) == ref_tf:
                return True
    return False


def _trend_filter_refs_for_tf(tf_name: str) -> list[str]:
    """Return the enabled trend-filter TFs relevant to this order TF."""
    refs: list[str] = []
    per_tf_map = getattr(config, "TREND_FILTER_PER_TF", {}) or {}
    if per_tf_map.get(tf_name, False):
        refs.append(tf_name)
    if getattr(config, "TREND_FILTER_HIGHER_TF_ENABLED", False):
        higher_tf = getattr(config, "TREND_FILTER_HIGHER_TF", "")
        if higher_tf and higher_tf not in refs:
            refs.append(higher_tf)
    return refs


def _trend_filter_trail_override(ticket: int, pos_type: str, order_tf: str) -> tuple[bool, str]:
    """
    Allow Trail SL to bypass Focus Opposite only when trend filter truly flips side:
    - SELL expects BEAR/SIDEWAY -> BULL
    - BUY expects BULL/SIDEWAY -> BEAR
    UNKNOWN does not count as a new trend and does not clear prior direction.
    """
    if not getattr(config, "TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED", True):
        return False, ""
    refs = _trend_filter_refs_for_tf(order_tf)
    if not refs:
        return False, ""
    try:
        import scanner
        swing_data = getattr(scanner, "_swing_data", {}) or {}
    except Exception:
        return False, ""

    expected_prev = "BEAR" if pos_type == "SELL" else "BULL"
    expected_new = "BULL" if pos_type == "SELL" else "BEAR"
    for ref_tf in refs:
        sw = swing_data.get(ref_tf) or {}
        trend = sw.get("trend") or {}
        t = trend.get("trend", "UNKNOWN")
        strength = trend.get("strength", "-")
        label = trend.get("label", t)
        if t == "UNKNOWN":
            continue

        key = f"{ticket}|{ref_tf}"
        prev = _trend_filter_last_dir.get(key)

        if t == "SIDEWAY":
            _trend_filter_last_dir[key] = t
            continue

        if t not in ("BULL", "BEAR") or strength not in ("weak", "strong"):
            continue

        _trend_filter_last_dir[key] = t
        if prev in (expected_prev, "SIDEWAY") and t == expected_new:
            return True, f"Trend Filter {ref_tf}: {expected_prev} -> {label}"
    return False, ""


def _reversal_trail_override(pos_type: str, order_tf: str, current_sl: float, pos_time: int = 0) -> tuple[bool, float, str]:
    """
    เมื่อเจอแท่งจุดกลับตัวฝั่งตรงข้าม ให้ lookback หา Main Engulf ล่าสุด
    ที่อยู่ก่อนแท่งจุดกลับตัว แล้วใช้ SL จาก engulf นั้น

    BUY  → เจอ Red Rejection/Engulf → หา Green Engulf ก่อนหน้า → SL = engulf.low − 1.0
    SELL → เจอ Green Rejection/Engulf → หา Red Engulf ก่อนหน้า → SL = engulf.high + 1.0
    """
    if not getattr(config, "TRAIL_SL_REVERSAL_OVERRIDE_ENABLED", False):
        return False, 0.0, ""

    tf_val = TF_OPTIONS.get(order_tf, mt5.TIMEFRAME_M1)
    lookback = min(TF_LOOKBACK.get(order_tf, SWING_LOOKBACK), 50)
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, lookback)
    if rates is None or len(rates) < 2:
        return False, 0.0, ""

    # กรอง bars ตั้งแต่ entry bar เป็นต้นไป
    bars = [r for r in rates if pos_time == 0 or int(r["time"]) >= pos_time]
    if len(bars) < 2:
        return False, 0.0, ""

    # ตรวจแท่งปิดล่าสุด (= แท่งจุดกลับตัว)
    cur  = bars[-1]
    prev = bars[-2]
    cur_o  = float(cur["open"])
    cur_c  = float(cur["close"])
    cur_h  = float(cur["high"])
    cur_l  = float(cur["low"])
    prev_h = float(prev["high"])
    prev_l = float(prev["low"])

    reversal_found = False
    reversal_type  = ""

    if pos_type == "BUY":
        if cur_c < cur_o:  # Red candle
            if cur_c < prev_l:
                reversal_found = True
                reversal_type  = "red engulf"
            elif cur_l < prev_l and prev_l <= cur_c <= prev_h:
                reversal_found = True
                reversal_type  = "red rejection"
    else:
        if cur_c > cur_o:  # Green candle
            if cur_c > prev_h:
                reversal_found = True
                reversal_type  = "green engulf"
            elif cur_h > prev_h and prev_l <= cur_c <= prev_h:
                reversal_found = True
                reversal_type  = "green rejection"

    if not reversal_found:
        return False, 0.0, ""

    # lookback หา Main Engulf ล่าสุดที่อยู่ก่อนแท่งจุดกลับตัว
    # ค้นใน bars[1 : len-1] (ข้าม entry bar, ไม่รวม reversal bar)
    reversal_idx = len(bars) - 1
    best_sl = 0.0
    best_label = ""

    for i in range(1, reversal_idx):
        b    = bars[i]
        bprev = bars[i - 1]
        b_c  = float(b["close"])
        b_o  = float(b["open"])
        b_h  = float(b["high"])
        b_l  = float(b["low"])
        ph   = float(bprev["high"])
        pl   = float(bprev["low"])

        if pos_type == "BUY":
            # Green Engulf: bull candle, close > prev_high
            if b_c > b_o and b_c > ph:
                candidate = round(b_l - 1.0, 2)
                if candidate > best_sl:
                    best_sl    = candidate
                    best_label = f"[{order_tf}] green engulf before {reversal_type}"
        else:
            # Red Engulf: bear candle, close < prev_low
            if b_c < b_o and b_c < pl:
                candidate = round(b_h + 1.0, 2)
                if best_sl == 0.0 or candidate < best_sl:
                    best_sl    = candidate
                    best_label = f"[{order_tf}] red engulf before {reversal_type}"

    if best_sl == 0.0:
        return False, 0.0, ""

    # SL ใหม่ต้องดีกว่า SL เดิม
    if pos_type == "BUY" and best_sl <= current_sl:
        return False, 0.0, ""
    if pos_type == "SELL" and current_sl > 0 and best_sl >= current_sl:
        return False, 0.0, ""

    return True, best_sl, f"reversal override {best_label}"


def reset_focus_frozen_side(feature: str):
    """Call this when the user toggles Focus Opposite from OFF back to ON."""
    if feature in _focus_frozen_side and _focus_frozen_side[feature] is not None:
        _focus_frozen_side[feature] = None
        try:
            save_runtime_state()
        except Exception:
            pass


def _get_spread_price():
    """Return spread as a price value."""
    info = mt5.symbol_info(SYMBOL)
    if not info:
        return 0.0
    try:
        return float(info.spread) * float(info.point)
    except Exception:
        return 0.0


def _fmt_bkk_ts(ts: int | float | None) -> str:
    """Convert an MT5 server timestamp to Bangkok display time."""
    return fmt_mt5_bkk_ts(ts)


def _tp_valid_for_side(pos_type: str, entry: float, tp: float, tol: float = 0.0) -> bool:
    if pos_type == "BUY":
        return tp >= entry - tol
    return tp <= entry + tol


def _entry_update_msg(title: str, sig_e: str, ticket: int, sl: float, sl_note: str,
                      tp: float | None = None, tp_note: str = "") -> str:
    lines = [
        title,
        f"{sig_e} Ticket:`{ticket}`",
        f"🛑 SL: `{sl}` ({sl_note})",
    ]
    if config.ENTRY_CANDLE_UPDATE_TP and tp is not None:
        tail = f" ({tp_note})" if tp_note else ""
        lines.append(f"🎯 TP: `{tp}`{tail}")
    return "\n".join(lines)


async def _run_limit_sweep_followup(app, ticket: int, pos_type: str, tf: str,
                                    rates, bar, prev_bar, reason_detail: str) -> None:
    """Continue Limit Sweep flow after a position is closed (cancel limits / place S8)."""
    now = now_bkk().strftime("%H:%M:%S")
    bar_close = float(bar["close"])
    bar_time = int(bar["time"])

    sh_info = _get_s6_prev_swing_high(rates, tf=tf)
    sl_info = _get_s6_prev_swing_low(rates, tf=tf)

    if pos_type == "BUY":
        target_info = _find_ll(rates, sl_info)
        while target_info and bar_close <= float(target_info["price"]):
            target_info = _find_ll(rates, target_info)
        target_price = target_info["price"] if target_info else None
    else:
        target_info = _find_hh(rates, sh_info)
        while target_info and bar_close >= float(target_info["price"]):
            target_info = _find_hh(rates, target_info)
        target_price = target_info["price"] if target_info else None

    h_price = sh_info["price"] if sh_info else None
    l_price = sl_info["price"] if sl_info else None
    orders = mt5.orders_get(symbol=SYMBOL)
    in_range_limits = []
    if orders:
        for o in orders:
            o_info = pending_order_tf.get(o.ticket)
            o_tf = o_info.get("tf") if isinstance(o_info, dict) else o_info
            if o_tf != tf:
                continue
            o_sid = o_info.get("sid") if isinstance(o_info, dict) else None
            ep = o.price_open
            if pos_type == "BUY" and o.type == mt5.ORDER_TYPE_BUY_LIMIT:
                in_rng = target_price and h_price and target_price <= ep <= h_price
                if in_rng or o_sid == 8:
                    in_range_limits.append(o)
            elif pos_type == "SELL" and o.type == mt5.ORDER_TYPE_SELL_LIMIT:
                in_rng = target_price and l_price and l_price <= ep <= target_price
                if in_rng or o_sid == 8:
                    in_range_limits.append(o)

    kept_ticket = None
    if target_price and in_range_limits:
        in_range_limits.sort(key=lambda o: abs(o.price_open - target_price))
        kept_ticket = in_range_limits[0].ticket
        for o in in_range_limits[1:]:
            r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
            ok_cancel = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
            status = "OK" if ok_cancel else "FAIL"
            print(f"[{now}] SWEEP cancel {pos_type} LIMIT #{o.ticket} [{tf}] entry={o.price_open:.2f} {status}")
            pending_order_tf.pop(o.ticket, None)
        rng = f"{'LL' if pos_type == 'BUY' else 'L'}-{'H' if pos_type == 'BUY' else 'HH'}"
        print(f"[{now}] SWEEP keep #{kept_ticket} [{tf}] near {'LL' if pos_type == 'BUY' else 'HH'}={target_price:.2f} (range {rng})")

    if target_info and not kept_ticket:
        candle = target_info.get("candle", {})
        c_high = candle.get("high", 0)
        c_low = candle.get("low", 0)
        c_range = c_high - c_low

        if c_range > 0:
            from mt5_utils import open_order
            if pos_type == "BUY":
                s8_entry = round(c_low - c_range * 0.17, 2)
                s8_sl = round(c_low - c_range * 0.31, 2)
                s8_tp = sh_info["price"] if sh_info else round(c_high, 2)
                s8_signal = "BUY"
            else:
                s8_entry = round(c_high + c_range * 0.17, 2)
                s8_sl = round(c_high + c_range * 0.31, 2)
                s8_tp = sl_info["price"] if sl_info else round(c_low, 2)
                s8_signal = "SELL"

            s8_pattern = f"ท่าที่ 8 กินไส้ Swing [Limit Sweep] {'🟢 BUY' if s8_signal == 'BUY' else '🔴 SELL'}"
            vol = config.get_volume()
            res = open_order(s8_signal, vol, s8_sl, s8_tp,
                             entry_price=s8_entry, tf=tf, sid="8", pattern=s8_pattern)
            if res.get("success"):
                s8_ticket = res["ticket"]
                pending_order_tf[s8_ticket] = {
                    "tf": tf, "signal": s8_signal,
                    "detect_bar_time": bar_time,
                    "sid": 8, "pattern": s8_pattern,
                    "source": "limit_sweep",
                    "swing_price": target_price,
                    "swing_bar_time": int(target_info.get("time", 0)),
                }
                position_pattern[s8_ticket] = s8_pattern
                log_event(
                    "ORDER_CREATED",
                    s8_pattern,
                    tf=tf,
                    sid=8,
                    signal=s8_signal,
                    entry=s8_entry,
                    sl=s8_sl,
                    tp=s8_tp,
                    ticket=s8_ticket,
                    order_type=res.get("order_type", "LIMIT"),
                    source="limit_sweep",
                    from_ticket=ticket,
                )
                print(f"[{now}] SWEEP -> S8 {s8_signal} LIMIT #{s8_ticket} [{tf}] "
                      f"Entry={s8_entry:.2f} SL={s8_sl:.2f} TP={s8_tp:.2f} "
                      f"{'LL' if pos_type == 'BUY' else 'HH'}={target_price:.2f}")
                await tg(app,
                    f"🧹 *Limit Sweep -> S8*\n"
                    f"ปิด {pos_type} `#{ticket}` [{tf}]\n"
                    f"{reason_detail}\n\n"
                    f"ตั้ง {s8_signal} LIMIT `#{s8_ticket}`\n"
                    f"📌 Entry: `{s8_entry:.2f}`\n"
                    f"🛑 SL: `{s8_sl:.2f}` | 🎯 TP: `{s8_tp:.2f}`\n"
                    f"{'📉 LL' if pos_type == 'BUY' else '📈 HH'}: `{target_price:.2f}`"
                )
            else:
                err = res.get("error", "?")
                print(f"[{now}] SWEEP S8 failed: {err}")
                await tg(app,
                    f"🧹 *Limit Sweep*\n"
                    f"ปิด {pos_type} `#{ticket}` [{tf}]\n"
                    f"{reason_detail}\n\n"
                    f"⚠️ S8 {'LL' if pos_type == 'BUY' else 'HH'} ตั้งไม่สำเร็จ: {err}"
                )
        else:
            await tg(app,
                f"🧹 *Limit Sweep*\n"
                f"ปิด {pos_type} `#{ticket}` [{tf}]\n"
                f"{reason_detail}\n\n"
                f"{'📉 LL' if pos_type == 'BUY' else '📈 HH'}: `{target_price:.2f}` (range=0 ข้าม S8)"
            )
    else:
        sweep_msg = ""
        if kept_ticket:
            sweep_msg = f"\nเหลือ LIMIT `#{kept_ticket}` ใกล้ {'LL' if pos_type == 'BUY' else 'HH'}"
        elif target_price:
            sweep_msg = f"\nไม่มี LIMIT ใน TF"
        await tg(app,
            f"🧹 *Limit Sweep*\n"
            f"ปิด {pos_type} `#{ticket}` [{tf}]\n"
            f"{reason_detail}{sweep_msg}"
        )


# -------------------------------------------------------------
async def check_limit_fill_notify(app):
    """
    แจ้งเตือน Limit Fill — independent จาก ENTRY_CANDLE_ENABLED
    ทำงานทุกครั้งที่มี position fill ใหม่ (ทำงานก่อน RSI Recheck)
    Skip: sid=13 (S13 มี notification ของตัวเอง), S12 (มี flow แยก)
    First-run guard: suppress positions ที่อายุเกิน _FILL_INIT_SUPPRESS_SEC (กัน re-notify หลัง restart)
    """
    global _fill_initialized
    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        return

    # First run: suppress only truly old positions
    if not _fill_initialized:
        _fill_initialized = True
        now_ts = int(datetime.now(timezone.utc).timestamp())
        for p in positions:
            fill_age = max(0, now_ts - int(getattr(p, "time", 0) or 0))
            if fill_age >= _FILL_INIT_SUPPRESS_SEC:
                _fill_notified[p.ticket] = True

    now = now_bkk().strftime("%H:%M:%S")
    for pos in positions:
        ticket = pos.ticket
        if ticket in _fill_notified:
            continue
        sid = position_sid.get(ticket)
        if sid in (12, 13):
            _fill_notified[ticket] = True   # mark to skip future calls
            continue
        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        sig_e = "🟢" if pos_type == "BUY" else "🔴"
        fvg_info = fvg_order_tickets.get(ticket)
        pattern_name = position_pattern.get(ticket, "") or ""
        reverse_tag = " [Reverse]" if pattern_name.startswith("Reverse ") else ""

        # ── resolve _fill_tf (3-tier fallback) ──
        _fill_tf = position_tf.get(ticket)
        if not _fill_tf and fvg_info:
            _fill_tf = fvg_info.get("tf")
        if not _fill_tf:
            # ลอง pending_order_tf (อาจยังมีอยู่ถ้า cleanup ยังไม่ pop)
            _pend_info_fill = pending_order_tf.get(ticket)
            if isinstance(_pend_info_fill, dict):
                _fill_tf = _pend_info_fill.get("tf")
                if not pattern_name and _pend_info_fill.get("pattern"):
                    pattern_name = _pend_info_fill["pattern"]
        if not _fill_tf:
            # parse comment ของ position เช่น "M30_S2" → tf="M30"
            _c_tf, _c_sid, _ = _infer_position_meta_from_comment(pos)
            if _c_tf:
                _fill_tf = _c_tf
                position_tf[ticket] = _c_tf      # cache กลับเข้า dict
                if not sid and _c_sid is not None:
                    sid = _c_sid
                # สร้าง pattern name พื้นฐานจาก sid+signal ถ้ายังไม่มี
                if not pattern_name and _c_sid is not None:
                    _sid_label = {1: "S1", 2: "S2 FVG", 3: "S3 DM SP", 4: "S4 FVG", 6: "S6", 7: "S6i", 8: "S8", 9: "S9 RSI Div", 10: "S10 MTF", 11: "S11 Fibo"}.get(_c_sid, f"S{_c_sid}")
                    pattern_name = f"{_sid_label} {pos_type} [{_c_tf}]"
        # fallback 4: tracked_positions (persisted across bot restarts → แก้ pattern=- หลัง restart)
        if not _fill_tf or not pattern_name or sid is None:
            _tp_info = getattr(config, "tracked_positions", {}).get(ticket) or {}
            if _tp_info:
                if not pattern_name and _tp_info.get("pattern"):
                    pattern_name = _tp_info["pattern"]
                if not _fill_tf and _tp_info.get("tf"):
                    _fill_tf = _tp_info["tf"]
                    position_tf[ticket] = _fill_tf          # cache กลับเข้า dict
                if sid is None and _tp_info.get("sid") is not None:
                    sid = _tp_info["sid"]
                    position_sid[ticket] = sid              # cache กลับเข้า dict
        if not _fill_tf:
            _fill_tf = "M1"                      # last-resort fallback
        try:
            from scanner import get_trend_label as _gtl
            _fill_trend = _gtl(_fill_tf)
            if _fill_trend == "?":
                # fallback: fetch HHLL ตรงโดยไม่รอ auto_scan (กรณี scan ยังไม่รันรอบแรก)
                try:
                    import hhll_swing as _hs
                    _hs.fetch_hhll(_fill_tf)
                    _tinfo = _hs.get_trend_from_structure(_fill_tf)
                    if _tinfo and _tinfo.get("trend") not in (None, "UNKNOWN"):
                        _t = _tinfo.get("trend", "")
                        _s = _tinfo.get("strength", "")
                        _fill_trend = f"{_t} ({_s})" if _s and _s != "-" else _t
                        # append HHLL last_label ถ้า SIDEWAY
                        if _t == "SIDEWAY":
                            _hhll_d = _hs.get_hhll_data(_fill_tf) or {}
                            _last_l = _hhll_d.get("last_label", "")
                            if _last_l:
                                _fill_trend = f"SIDEWAY/{_last_l}"
                except Exception:
                    pass
        except Exception:
            _fill_trend = "?"

        _fill_notified[ticket] = True
        fill_time = _fmt_bkk_ts(int(pos.time))

        # RSI value ณ เวลา fill
        _fill_rsi_val  = _latest_pending_rsi(_fill_tf)
        _fill_rsi_str  = f"{_fill_rsi_val:.2f}" if _fill_rsi_val is not None else "?"

        # RSI Mode 2 state (crossover)
        _fill_rsi2_state = _rsi2_get_state(_fill_tf) if _fill_rsi_val is not None else "?"

        # RSI cross label
        _rsi2_emoji = {"SELL_ONLY": "🔴 SELL_ONLY", "BUY_ONLY": "🟢 BUY_ONLY", "ANY": "⚪ ANY"}.get(
            _fill_rsi2_state, f"? {_fill_rsi2_state}"
        )

        # PD EQ ณ เวลา fill
        try:
            from hhll_swing import get_swing_hl_pts as _gshl_fill
            _fsh, _fsl = _gshl_fill(_fill_tf)
            _fill_pd_h = float(_fsh["price"]) if _fsh else None
            _fill_pd_l = float(_fsl["price"]) if _fsl else None
        except Exception:
            _fill_pd_h = _fill_pd_l = None
        if _fill_pd_h and _fill_pd_l:
            _fill_eq     = round((_fill_pd_h + _fill_pd_l) / 2.0, 2)
            _fill_eq_str = (f"H:`{_fill_pd_h:.2f}` L:`{_fill_pd_l:.2f}` EQ:`{_fill_eq:.2f}`")
        else:
            _fill_eq_str = "—"

        # S14: ดึง ref_source + sub_pattern จาก pend_info
        _s14_ref_source  = None
        _s14_sub_pattern = None
        if sid == 14:
            _s14_pend = pending_order_tf.get(ticket) or {}
            _s14_ref_source  = _s14_pend.get("s14_ref_source")
            _s14_sub_pattern = _s14_pend.get("s14_sub_pattern")

        log_event(
            "ENTRY_FILL",
            "Limit fill detected",
            ticket=ticket,
            side=pos_type,
            tf=_fill_tf,
            sid=sid,
            pattern=pattern_name,
            price=pos.price_open,
            sl=pos.sl,
            tp=pos.tp,
            fill_time=fill_time,
            trend=_fill_trend,
            rsi=_fill_rsi_val,
            rsi2_state=_fill_rsi2_state,
            pd_h=_fill_pd_h,
            pd_l=_fill_pd_l,
            pd_eq=_fill_eq if (_fill_pd_h and _fill_pd_l) else None,
            **({"ref_source": _s14_ref_source,
                "sub_pattern": _s14_sub_pattern}
               if sid == 14 and (_s14_ref_source or _s14_sub_pattern) else {}),
        )
        await tg(app, (
            f"🔔 *Limit Fill - {pos_type}{reverse_tag}*\n"
            f"{sig_e} Ticket:`{ticket}`\n"
            f"📝 Pattern: `{pattern_name or '-'}`\n"
            f"📌 เปิดที่: `{pos.price_open:.2f}`\n"
            f"🛑 SL: `{pos.sl:.2f}` | 🎯 TP: `{pos.tp:.2f}`\n"
            f"🕐 Fill Time: `{fill_time}`\n"
            f"📈 Trend: `{_fill_tf}` → `{_fill_trend}`\n"
            f"📊 RSI({config.PENDING_RSI_PERIOD}): `{_fill_rsi_str}` | Cross: `{_rsi2_emoji}`\n"
            f"⚖️ PD [{_fill_tf}]: {_fill_eq_str}"
        ))
        print(f"[{now}] fill {pos_type} {ticket}={pos.price_open:.2f}")


# -------------------------------------------------------------
async def check_fill_rsi_recheck(app):
    """
    RSI Fill Recheck — เช็ค RSI ตอน position เพิ่ง fill (independent จาก Entry Candle Mode)
    Gate: `PENDING_RSI_RECHECK_ENABLED`
    Rule:
      BUY  → ต้อง RSI < PENDING_RSI_BUY_MAX (default 50) ไม่งั้นปิด position
      SELL → ต้อง RSI > PENDING_RSI_SELL_MIN (default 50) ไม่งั้นปิด position
    Skip: -
    """
    if not getattr(config, "PENDING_RSI_RECHECK_ENABLED", False):
        return
    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        _pending_rsi_close.clear()
        return

    open_pos_tickets = {p.ticket for p in positions}
    for _t in list(_pending_rsi_close):
        if _t not in open_pos_tickets:
            _pending_rsi_close.pop(_t, None)

    now = now_bkk().strftime("%H:%M:%S")
    for pos in positions:
        ticket = pos.ticket
        if ticket in _fill_rsi_checked:
            continue
        sid = position_sid.get(ticket)
        if sid in (1, 9, 11, 14, 15, 16, 17, 18, 19, 20, 20.5, 20.6, 20.7):
            continue  # S1 (zone-based), S9 (RSI Div), S11 (Fibo), S14 (Sweep RSI), S15 (VP reversal — RSI มัก extreme), S17 (Sweep Sniper — เข้าที่ RSI extreme by design), S18 (TJR standalone), S19 (ICT SB standalone) — skip RSI Recheck
        # S12, S13 — ใช้ RSI Recheck (ตามคำขอ 2026-05-18)
        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        sig_e = "🟢" if pos_type == "BUY" else "🔴"

        # ── Pending close retry (ทุก cycle จนกว่าจะปิดได้) ────────────────────
        if ticket in _pending_rsi_close:
            ok, cp = _close_position(pos, pos_type, "fill rsi pending retry")
            if ok:
                _pending_rsi_close.pop(ticket, None)
                _fill_rsi_checked.add(ticket)
                await tg(app, f"✅ *RSI Recheck retry ปิดสำเร็จ*\n{sig_e} Ticket:`{ticket}` ปิดที่`{cp}`")
                print(f"[{now}] fill_rsi_retry_close {pos_type} {ticket} @ {cp}")
            continue
        fvg_info = fvg_order_tickets.get(ticket)
        pattern_name = position_pattern.get(ticket, "") or ""
        # ── resolve _fill_tf (3-tier fallback, same as check_limit_fill_notify) ──
        _fill_tf = position_tf.get(ticket)
        if not _fill_tf and fvg_info:
            _fill_tf = fvg_info.get("tf")
        if not _fill_tf:
            _pend_info_fill = pending_order_tf.get(ticket)
            if isinstance(_pend_info_fill, dict):
                _fill_tf = _pend_info_fill.get("tf")
        if not _fill_tf:
            _c_tf, _c_sid, _ = _infer_position_meta_from_comment(pos)
            if _c_tf:
                _fill_tf = _c_tf
                position_tf[ticket] = _c_tf
        if not _fill_tf:
            _fill_tf = "M1"

        # Route ตาม mode — 1=mode1, 2=mode2, 3=ทั้งคู่
        _mode = int(getattr(config, "PENDING_RSI_RECHECK_MODE", 1))

        _r1 = _pending_rsi_rule_result(pos_type, _fill_tf)  if _mode in (1, 3) else None
        _r2 = _pending_rsi_mode2_result(pos_type, _fill_tf) if _mode in (2, 3) else None

        # ถ้าข้อมูล RSI ไม่พร้อมทุก mode ที่เลือก → skip รอรอบหน้า
        if (_mode == 1 and _r1 is None) or \
           (_mode == 2 and _r2 is None) or \
           (_mode == 3 and _r1 is None and _r2 is None):
            log_event(
                "ENTRY_FILL_RSI_RECHECK_SKIP",
                "RSI unavailable after fill",
                ticket=ticket,
                side=pos_type,
                tf=_fill_tf,
                sid=sid,
                pattern=pattern_name,
            )
            continue

        # รวบ fail reasons (ถ้ามี)
        _fail_parts = []
        _rsi_val = None

        if _r1 is not None:
            _rsi_val = _r1["rsi"]
            if not _r1["allowed"]:
                _fail_parts.append(
                    f"[Mode1] ไม่ผ่าน {_r1['rule']} "
                    f"(BUY<{_r1['threshold_text']} / SELL>{_r1['threshold_text']})"
                )

        if _r2 is not None:
            _rsi_val = _rsi_val or _r2["rsi"]
            if not _r2["allowed"]:
                _state = _r2.get("state", "?")
                _fail_parts.append(
                    f"[Mode2] State={_state} → block {pos_type} | {_r2['threshold_text']}"
                )

        rsi_passed = len(_fail_parts) == 0

        if _triple_check_all_enabled():
            # ── Triple mode: record RSI result และให้ combined evaluator ตัดสิน ──
            _triple_check_record(ticket, "rsi", rsi_passed,
                                 tf=_fill_tf, signal=pos_type)
            _rsi_str = f"{_rsi_val:.2f}" if _rsi_val is not None else "-"
            await tg(app, (
                f"📊 *RSI Fill Recheck (Triple mode)*\n"
                f"{sig_e} Ticket:`{ticket}` [{pos_type}] `{_fill_tf}`\n"
                f"📊 RSI({config.PENDING_RSI_PERIOD}): `{_rsi_str}`\n"
                f"ผล: {'✅ PASS' if rsi_passed else '❌ FAIL'}"
            ))
            tc_dec = _triple_check_evaluate(ticket)
            if tc_dec == "cancel":
                tc_st = _triple_check_state.pop(ticket, {})
                _reason = (
                    f"Triple Recheck < 2/3: "
                    f"RSI {_triple_r(tc_st.get('rsi'))} "
                    f"Trend {_triple_r(tc_st.get('trend'))} "
                    f"PD {_triple_r(tc_st.get('pd'))}"
                )
                log_event("TRIPLE_RECHECK_FAIL", _reason, ticket=ticket,
                          side=pos_type, tf=_fill_tf)
                ok_close, close_price = _close_position(pos, pos_type, "triple recheck fail")
                status = "ส่งปิดแล้ว" if ok_close else "ส่งปิดไม่สำเร็จ"
                await tg(app, (
                    f"⚠️ *Triple Recheck < 2/3 — ปิด position*\n"
                    f"{sig_e} Ticket:`{ticket}` [{pos_type}] `{_fill_tf}`\n"
                    f"RSI {_triple_r(tc_st.get('rsi'))} | "
                    f"Trend {_triple_r(tc_st.get('trend'))} | "
                    f"PD {_triple_r(tc_st.get('pd'))}\n"
                    f"สถานะ: `{status}`"
                ))
                if ok_close:
                    _fill_rsi_checked.add(ticket)
                    print(f"[{now}] triple_recheck_close {pos_type} {ticket} close={close_price:.2f}")
                else:
                    _pending_rsi_close[ticket] = pos_type
            elif tc_dec == "keep":
                tc_st = _triple_check_state.pop(ticket, {})
                _tc_line = (
                    f"RSI {_triple_r(tc_st.get('rsi'))} | "
                    f"Trend {_triple_r(tc_st.get('trend'))} | "
                    f"PD {_triple_r(tc_st.get('pd'))}"
                )
                log_event(
                    "TRIPLE_RECHECK", "KEEP",
                    ticket=ticket, tf=_fill_tf,
                    rsi=tc_st.get("rsi"), trend=tc_st.get("trend"), pd=tc_st.get("pd"),
                )
                await tg(app, (
                    f"✅ *Triple Recheck ผ่าน 2/3 — Keep Position*\n"
                    f"{sig_e} Ticket:`{ticket}` [{pos_type}] `{_fill_tf}`\n"
                    f"{_tc_line}"
                ))
                _fill_rsi_checked.add(ticket)
            # tc_dec == "wait" → ยังรอผลจาก check อื่น ไม่ทำอะไร
        elif _fail_parts:
            # ── Individual mode: RSI fail → close ทันที ──
            _reason = (
                f"Fill RSI Recheck Fail [{_fill_tf}]: {pos_type} entry:{float(pos.price_open):.2f} | "
                f"RSI({config.PENDING_RSI_PERIOD})={_rsi_val:.2f} | "
                + " | ".join(_fail_parts)
            )
            log_event(
                "ENTRY_FILL_RSI_RECHECK_FAIL",
                _reason,
                ticket=ticket,
                side=pos_type,
                tf=_fill_tf,
                sid=sid,
                pattern=pattern_name,
                price=pos.price_open,
                rsi=_rsi_val,
                mode=_mode,
            )
            ok_close, close_price = _close_position(pos, pos_type, f"fill rsi fail [{_fill_tf}]")
            status = "ส่งปิดแล้ว" if ok_close else "ส่งปิดไม่สำเร็จ"
            _fail_text = "\n".join(f"  • {p}" for p in _fail_parts)
            await tg(app, (
                f"⚠️ *Fill RSI Recheck ไม่ผ่าน - ปิดทันที* (Mode {_mode})\n"
                f"{sig_e} Ticket:`{ticket}` [{pos_type}]\n"
                f"📝 Pattern: `{pattern_name or '-'}`\n"
                f"📍 TF: `{_fill_tf}`\n"
                f"📌 Entry: `{float(pos.price_open):.2f}`\n"
                f"📊 RSI({config.PENDING_RSI_PERIOD}): `{_rsi_val:.2f}`\n"
                f"❌ เหตุผล:\n{_fail_text}\n"
                f"สถานะ: `{status}`"
            ))
            if ok_close:
                _fill_rsi_checked.add(ticket)
                print(f"[{now}] fill_rsi_close {pos_type} {ticket} close={close_price:.2f}")
            else:
                _pending_rsi_close[ticket] = pos_type
        else:
            _fill_rsi_checked.add(ticket)


# -------------------------------------------------------------
async def check_fill_trend_recheck(app):
    """Trend Recheck หลัง fill: ตรวจ trend ของ position ที่เพิ่ง fill
    Gate: LIMIT_TREND_RECHECK
    Skip: S9 (RSI Div), S10 (CRT), S14 (Sweep RSI)

    รอบ 1 : เช็คทุกรอบสแกน (~5s) หลัง fill จนกว่าข้อมูลพร้อม
             ถ้า trend สวนทาง → ปิด position (retry ทุก cycle ถ้า close ล้มเหลว)
             ถ้าผ่าน → บันทึก round2_start_time = pivot_time + HHLL_RIGHT × tf_secs

    รอบ 2 : เริ่มเช็คเมื่อถึง round2_start_time (pivot confirm time)
             เช็คทุกรอบสแกนจนกว่า swing ใหม่จะปรากฏ (sh/sl เปลี่ยน)
             ถ้า trend สวนทาง → ปิด position
    """
    if not getattr(config, "LIMIT_TREND_RECHECK", False):
        return
    positions = mt5.positions_get(symbol=SYMBOL)
    if positions is None:
        return  # MT5 error / ขาด connection — ไม่ clear state เพื่อป้องกัน fill_round1 วิ่งซ้ำ
    if not positions:
        _trend_recheck_state.clear()
        _fill_trend_checked.clear()
        return

    import time as _time
    import hhll_swing as _hs

    open_pos_tickets = {p.ticket for p in positions}

    # Cleanup state สำหรับ position ที่ปิดไปแล้ว
    for _t in list(_trend_recheck_state.keys()):
        if _t not in open_pos_tickets:
            _trend_recheck_state.pop(_t, None)
    _fill_trend_checked.difference_update(
        _t for _t in list(_fill_trend_checked) if _t not in open_pos_tickets
    )

    ltr_rounds = int(getattr(config, "LIMIT_TREND_RECHECK_ROUNDS", 2))
    from scanner import trend_allows_signal as _tas, swing_data_ready as _sdr
    from hhll_swing import get_swing_hl_pts as _ghl, get_hhll_data as _ghd

    for pos in positions:
        ticket = pos.ticket
        sid = position_sid.get(ticket)
        # Skip S1/S2/S3/S11 (ใช้ trend filter ของตัวเองที่ signal gen), S9/S10/S14/S15/S16/S17 (market order หรือ counter-trend by design), S18 (TJR standalone), S19 (ICT SB standalone)
        if sid in (1, 2, 3, 9, 10, 11, 14, 15, 16, 17, 18, 19, 20, 20.5, 20.6, 20.7):
            continue

        # ข้ามถ้าทุก round เสร็จแล้ว
        if ticket in _fill_trend_checked:
            continue

        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        sig_e    = "🟢" if pos_type == "BUY" else "🔴"

        # Resolve TF (3-tier fallback)
        _tr_tf = position_tf.get(ticket)
        if not _tr_tf:
            _fi = fvg_order_tickets.get(ticket)
            if _fi:
                _tr_tf = _fi.get("tf")
        if not _tr_tf:
            _tr_tf = "M1"
        # S2 parallel ใช้ composite TF เช่น "[M15_H1]" ที่ไม่มีใน _swing_data/_hhll_data
        # → เดิม swing_data_ready คืน False เสมอ → recheck skip เงียบ (ไม่มี protection เลย)
        # → resolve เป็น TF สูงสุดของคู่ เพื่อให้ trend recheck ทำงานได้
        if _tr_tf and _tr_tf.startswith("["):
            _tr_parts = re.findall(r"[MHD]\d+", _tr_tf)
            if _tr_parts:
                _tr_tf = max(_tr_parts, key=lambda t: int(TF_SECONDS_MAP.get(t, 0) or 0))

        tr_state = _trend_recheck_state.get(ticket)

        # ── Pending close retry (ทุก cycle จนกว่าจะปิดได้) ──────────────
        if tr_state and tr_state.get("pending_close"):
            _pc_rnd   = tr_state.get("pending_close_round", 1)
            _pc_total = tr_state.get("rounds_total", ltr_rounds)
            _pc_why   = tr_state.get("pending_close_why", "?")
            # Fetch fresh position ก่อน close — กัน stale pos.volume หลัง TSO partial close
            # (เดิมใช้ pos จาก positions_get ต้นฟังก์ชัน ซึ่งอาจ stale กว่า PD Zone ที่ fetch ใหม่)
            _fresh_pts = mt5.positions_get(ticket=ticket)
            _close_pos = _fresh_pts[0] if _fresh_pts else pos
            ok, cp = _close_position(
                _close_pos, pos_type,
                f"Fill Trend Recheck [round{_pc_rnd}/{_pc_total}] retry: trend={_pc_why}"
            )
            log_event("TREND_RECHECK", f"fill_close_round{_pc_rnd}_retry",
                      ticket=ticket, tf=_tr_tf, signal=pos_type,
                      why=_pc_why, ok=ok)
            if ok:
                log_event("TREND_RECHECK", f"fill_close_round{_pc_rnd}",
                          ticket=ticket, tf=_tr_tf, signal=pos_type,
                          why=_pc_why, close_price=cp)
                await tg(app, (
                    f"📊 *Trend Recheck: ปิด Position [round{_pc_rnd}/{_pc_total}]*\n"
                    f"{sig_e} Ticket:`{ticket}` [{_tr_tf}]\n"
                    f"Trend สวนทาง: `{_pc_why}`\n"
                    f"ปิดที่: `{cp:.2f}`"
                ))
                _trend_recheck_state.pop(ticket, None)
                _fill_trend_checked.add(ticket)
            continue

        # ── รอบ 1: เช็คทุก cycle จนกว่าข้อมูลพร้อม ──────────────────────
        if tr_state is None:
            # Pre-fill approach check ผ่านมาแล้ว → skip round 1 ใช้ approach-time swing เป็น baseline
            _approach_pre = _pending_trend_approach.pop(ticket, None)
            if _approach_pre:
                _r1_sh   = _approach_pre.get("round1_sh")
                _r1_sl   = _approach_pre.get("round1_sl")
                _r1_sh_t = _approach_pre.get("round1_sh_t", 0)
                _r1_sl_t = _approach_pre.get("round1_sl_t", 0)
                _r2_st   = _approach_pre.get("round2_start_time", int(_time.time()))
                _trend_recheck_state[ticket] = {
                    "round": 2,
                    "rounds_total": ltr_rounds,
                    "round2_start_time": _r2_st,
                    "round1_sh": _r1_sh,
                    "round1_sl": _r1_sl,
                    "pending_close": False,
                }
                log_event("TREND_RECHECK", "fill_round1_skip_approach_passed",
                          ticket=ticket, tf=_tr_tf, signal=pos_type,
                          sh=_r1_sh, sl=_r1_sl,
                          sh_t=_r1_sh_t, sl_t=_r1_sl_t)
                continue  # ไป round 2 รอบถัดไป

            # ถ้าข้อมูล swing ยังไม่พร้อม → force fetch HHLL ตรงแทนรอ scanner
            if not _sdr(_tr_tf):
                try:
                    from hhll_swing import fetch_hhll as _fhhll
                    _fhhll(_tr_tf)
                except Exception:
                    pass
                if not _sdr(_tr_tf):
                    continue
            _allowed, _why = _tas(_tr_tf, pos_type)
            # sentinel "?" = HHLL data ยังไม่พร้อม → force fetch แล้ว retry
            if _allowed and _why == "?":
                try:
                    from hhll_swing import fetch_hhll as _fhhll
                    _fhhll(_tr_tf)
                except Exception:
                    pass
                _allowed, _why = _tas(_tr_tf, pos_type)
                if _allowed and _why == "?":
                    continue

            # เช็ค last_label + swing direction ใน round1
            # BUY block: LL (low < prev low) หรือ HL ที่กำลังลด (hl < prev_hl)
            # SELL block: HH (high > prev high) หรือ LH ที่กำลังสูงขึ้น (lh > prev_lh)
            _hhll_d_r1   = _ghd(_tr_tf) or {}
            _last_lbl_r1 = _hhll_d_r1.get("last_label", "")
            if _allowed and _last_lbl_r1:
                _hl_r1      = _hhll_d_r1.get("hl") or {}
                _ll_r1      = _hhll_d_r1.get("ll") or {}
                _lh_r1      = _hhll_d_r1.get("lh") or {}
                _hh_r1      = _hhll_d_r1.get("hh") or {}
                _prev_hl_r1 = _hhll_d_r1.get("prev_hl") or {}
                _prev_lh_r1 = _hhll_d_r1.get("prev_lh") or {}
                if pos_type == "BUY":
                    if _last_lbl_r1 == "ll" and _ll_r1 and _hl_r1:
                        _allowed = False
                        _why = f"LL ({float(_ll_r1['price']):.2f} < {float(_hl_r1['price']):.2f})"
                    elif _last_lbl_r1 == "hl" and _hl_r1 and _prev_hl_r1:
                        if float(_hl_r1["price"]) < float(_prev_hl_r1["price"]):
                            _allowed = False
                            _why = f"HL ต่ำลง ({float(_hl_r1['price']):.2f} < {float(_prev_hl_r1['price']):.2f})"
                    elif _last_lbl_r1 == "lh" and _lh_r1 and _hh_r1:
                        _allowed = False
                        _why = f"LH ({float(_lh_r1['price']):.2f} < {float(_hh_r1['price']):.2f})"
                elif pos_type == "SELL":
                    if _last_lbl_r1 == "hh" and _hh_r1 and _lh_r1:
                        _allowed = False
                        _why = f"HH ({float(_hh_r1['price']):.2f} > {float(_lh_r1['price']):.2f})"
                    elif _last_lbl_r1 == "lh" and _lh_r1 and _prev_lh_r1:
                        if float(_lh_r1["price"]) > float(_prev_lh_r1["price"]):
                            _allowed = False
                            _why = f"LH สูงขึ้น ({float(_lh_r1['price']):.2f} > {float(_prev_lh_r1['price']):.2f})"
                    elif _last_lbl_r1 == "hl" and _hl_r1 and _ll_r1:
                        _allowed = False
                        _why = f"HL ({float(_hl_r1['price']):.2f} > {float(_ll_r1['price']):.2f})"

            log_event("TREND_RECHECK", "fill_round1",
                      ticket=ticket, tf=_tr_tf, signal=pos_type,
                      allowed=_allowed, why=_why, rounds_config=ltr_rounds)

            if not _allowed:
                ok, cp = _close_position(
                    pos, pos_type,
                    f"Fill Trend Recheck [round1/{ltr_rounds}]: trend={_why}"
                )
                if ok:
                    log_event("TREND_RECHECK", "fill_close_round1",
                              ticket=ticket, tf=_tr_tf, signal=pos_type,
                              why=_why, close_price=cp)
                    await tg(app, (
                        f"📊 *Trend Recheck: ปิด Position [round1/{ltr_rounds}]*\n"
                        f"{sig_e} Ticket:`{ticket}` [{_tr_tf}]\n"
                        f"Trend สวนทาง: `{_why}`\n"
                        f"ปิดที่: `{cp:.2f}`"
                    ))
                    _fill_trend_checked.add(ticket)
                else:
                    # close ล้มเหลว → retry ทุก cycle
                    log_event("TREND_RECHECK", "fill_close_round1_failed",
                              ticket=ticket, tf=_tr_tf, signal=pos_type, why=_why)
                    await tg(app, (
                        f"⚠️ *Trend Recheck: ปิด Position ล้มเหลว [round1/{ltr_rounds}]*\n"
                        f"{sig_e} Ticket:`{ticket}` [{_tr_tf}]\n"
                        f"Trend สวนทาง: `{_why}` — จะ retry ทุกรอบสแกน"
                    ))
                    _trend_recheck_state[ticket] = {
                        "round": 1,
                        "rounds_total": ltr_rounds,
                        "pending_close": True,
                        "pending_close_why": _why,
                        "pending_close_round": 1,
                    }

            elif ltr_rounds >= 2:
                # รอบ 1 ผ่าน → คำนวณ round2_start_time จาก pivot ล่าสุด + HHLL_RIGHT × tf_secs
                _hhll_d   = _hhll_d_r1  # reuse จาก round1 check ด้านบน
                _last_lbl = _hhll_d.get("last_label", "")
                _pivot_pt = _hhll_d.get(_last_lbl.lower()) if _last_lbl else None
                _piv_t    = int(_pivot_pt["time"]) if _pivot_pt and "time" in _pivot_pt else 0
                _tf_secs  = int(TF_SECONDS_MAP.get(_tr_tf, 300) or 300)
                _hhll_rb  = int(getattr(_hs, "HHLL_RIGHT", 5))
                _r2_start = (_piv_t + _hhll_rb * _tf_secs) if _piv_t else (int(_time.time()) + _hhll_rb * _tf_secs)
                _sh, _sl  = _ghl(_tr_tf)
                _trend_recheck_state[ticket] = {
                    "round": 2,
                    "rounds_total": ltr_rounds,
                    "round2_start_time": _r2_start,
                    "round1_sh": float(_sh["price"]) if _sh else None,
                    "round1_sl": float(_sl["price"]) if _sl else None,
                    "pending_close": False,
                }
                log_event("TREND_RECHECK", "fill_round1_pass_wait_pivot",
                          ticket=ticket, tf=_tr_tf, signal=pos_type,
                          pivot_label=_last_lbl,
                          round2_start=fmt_mt5_bkk_ts(_r2_start, "%H:%M:%S"),
                          rounds_total=ltr_rounds)
            else:
                # ltr_rounds == 1 and allowed → จบแล้ว
                _fill_trend_checked.add(ticket)
            continue

        # ── รอบ 2: time-based trigger, เช็คทุก cycle จนกว่า swing ใหม่จะเจอ ──
        if tr_state.get("round") != 2:
            continue

        # ยังไม่ถึงเวลา pivot confirm
        if _time.time() < tr_state.get("round2_start_time", 0):
            continue

        # รอ swing ใหม่ (sh/sl ต้องเปลี่ยนจาก round 1)
        # force fetch HHLL เพื่อได้ข้อมูลล่าสุดก่อนเช็ค — R1 ทำเหมือนกัน
        try:
            from hhll_swing import fetch_hhll as _fhhll
            _fhhll(_tr_tf)
        except Exception:
            pass
        _sh, _sl   = _ghl(_tr_tf)
        _new_h     = float(_sh["price"]) if _sh else None
        _new_l     = float(_sl["price"]) if _sl else None
        _r1_h      = tr_state.get("round1_sh")
        _r1_l      = tr_state.get("round1_sl")
        _h_chg     = (_new_h is not None and _r1_h is not None and abs(_new_h - _r1_h) > 0.01)
        _l_chg     = (_new_l is not None and _r1_l is not None and abs(_new_l - _r1_l) > 0.01)
        if not (_h_chg or _l_chg):
            continue  # swing ยังไม่เปลี่ยน → retry cycle ถัดไป

        _allowed, _why = _tas(_tr_tf, pos_type)
        if _allowed and _why == "?":
            continue  # HHLL ยังไม่พร้อม → retry

        # เช็คทิศทาง swing (ทุก trend mode) เทียบกับ baseline ของ round1
        # BUY block: LL (new_l < r1_l) หรือ LH (new_h < r1_h → resistance ลด)
        # SELL block: HH (new_h > r1_h) หรือ HL (new_l > r1_l → support ขึ้น)
        if _allowed:
            if pos_type == "BUY":
                if _l_chg and _new_l < _r1_l:
                    _allowed = False
                    _why = f"LL ({_new_l:.2f} < {_r1_l:.2f})"
                elif _h_chg and _new_h < _r1_h:
                    _allowed = False
                    _why = f"LH ({_new_h:.2f} < {_r1_h:.2f})"
            elif pos_type == "SELL":
                if _h_chg and _new_h > _r1_h:
                    _allowed = False
                    _why = f"HH ({_new_h:.2f} > {_r1_h:.2f})"
                elif _l_chg and _new_l > _r1_l:
                    _allowed = False
                    _why = f"HL ({_new_l:.2f} > {_r1_l:.2f})"

        _total   = tr_state.get("rounds_total", ltr_rounds)
        _changed = "/".join(p for p in ["H" if _h_chg else "", "L" if _l_chg else ""] if p)
        log_event("TREND_RECHECK", "fill_round2",
                  ticket=ticket, tf=_tr_tf, signal=pos_type,
                  allowed=_allowed, why=_why,
                  swing_changed=_changed, rounds_total=_total)

        if not _allowed:
            ok, cp = _close_position(
                pos, pos_type,
                f"Fill Trend Recheck [round2/{_total}]: swing changed ({_changed}), trend={_why}"
            )
            if ok:
                log_event("TREND_RECHECK", "fill_close_round2",
                          ticket=ticket, tf=_tr_tf, signal=pos_type,
                          why=_why, close_price=cp)
                await tg(app, (
                    f"📊 *Trend Recheck: ปิด Position [round2/{_total}]*\n"
                    f"{sig_e} Ticket:`{ticket}` [{_tr_tf}]\n"
                    f"Swing เปลี่ยน ({_changed}) → `{_why}`\n"
                    f"ปิดที่: `{cp:.2f}`"
                ))
                _trend_recheck_state.pop(ticket, None)
                _fill_trend_checked.add(ticket)
            else:
                log_event("TREND_RECHECK", "fill_close_round2_failed",
                          ticket=ticket, tf=_tr_tf, signal=pos_type, why=_why)
                await tg(app, (
                    f"⚠️ *Trend Recheck: ปิด Position ล้มเหลว [round2/{_total}]*\n"
                    f"{sig_e} Ticket:`{ticket}` [{_tr_tf}]\n"
                    f"Trend สวนทาง: `{_why}` — จะ retry ทุกรอบสแกน"
                ))
                tr_state["pending_close"]       = True
                tr_state["pending_close_why"]   = _why
                tr_state["pending_close_round"] = 2
                _trend_recheck_state[ticket]    = tr_state
        else:
            # ผ่านครบทุก round
            _trend_recheck_state.pop(ticket, None)
            _fill_trend_checked.add(ticket)
            log_event("TREND_RECHECK", "fill_all_rounds_pass",
                      ticket=ticket, tf=_tr_tf, rounds=_total)


# -------------------------------------------------------------
async def check_pending_trend_approach(app):
    """
    Pending Trend Check on Approach — เช็ค trend ของ pending order ก่อน fill
    เมื่อราคาเข้าใกล้ entry ≤ PENDING_TREND_CHECK_POINTS จุด:

    รอบ 1 (approach): เช็ค trend ทันที
        FAIL → ยกเลิก pending order (ก่อน fill → ไม่เสีย spread+slippage)
        PASS → บันทึก swing H/L ไว้ รอ round 2

    รอบ 2 (swing ใหม่): เมื่อ swing H/L เปลี่ยนจาก round 1
        FAIL → ยกเลิก pending (ถ้ายังไม่ fill)
               check_fill_trend_recheck จะ handle ต่อถ้า fill แล้ว
        PASS → clear state

    Gate: PENDING_TREND_CHECK_ENABLED
    Skip: S9, S10, S14, S15 (เหมือน check_fill_trend_recheck)
    """
    if not getattr(config, "PENDING_TREND_CHECK_ENABLED", False):
        return

    orders = mt5.orders_get(symbol=SYMBOL)
    if not orders:
        _pending_trend_approach.clear()
        return

    import time as _time
    import hhll_swing as _hs
    from scanner import trend_allows_signal as _tas, swing_data_ready as _sdr
    from hhll_swing import get_swing_hl_pts as _ghl, get_hhll_data as _ghd

    open_order_tickets = {int(o.ticket) for o in orders}
    open_pos_tickets   = {int(p.ticket) for p in (mt5.positions_get(symbol=SYMBOL) or [])}

    # Cleanup state สำหรับ ticket ที่ไม่มีแล้ว (ปิด/ยกเลิก และไม่ได้ fill)
    for _t in list(_pending_trend_approach.keys()):
        if _t not in open_order_tickets and _t not in open_pos_tickets:
            _pending_trend_approach.pop(_t, None)

    sym_info = mt5.symbol_info(SYMBOL)
    if not sym_info:
        return
    _pt            = sym_info.point or 0.01
    _approach_dist = getattr(config, "PENDING_TREND_CHECK_POINTS", 200) * _pt * config.points_scale()
    tick           = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        return

    ltr_rounds = int(getattr(config, "LIMIT_TREND_RECHECK_ROUNDS", 2))

    for order in orders:
        ticket = int(order.ticket)
        if order.type not in (mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_SELL_LIMIT):
            continue

        # Resolve SID
        sid = position_sid.get(ticket)
        if sid is None:
            _pend = pending_order_tf.get(ticket)
            if isinstance(_pend, dict):
                sid = _pend.get("sid")

        # Skip เหมือน check_fill_trend_recheck (S1/S2/S3/S11 ไม่ใช้ approach trend recheck), S18/S19 standalone
        if sid in (1, 2, 3, 9, 10, 11, 14, 15, 17, 18, 19, 20, 20.5, 20.6, 20.7):
            continue

        # Resolve TF
        _tf = position_tf.get(ticket)
        if not _tf:
            _pend = pending_order_tf.get(ticket)
            if isinstance(_pend, dict):
                _tf = _pend.get("tf")
        if not _tf:
            _tf = "M1"
        if _tf.startswith("["):
            _parts = re.findall(r"[MHD]\d+", _tf)
            if _parts:
                _tf = max(_parts, key=lambda t: int(TF_SECONDS_MAP.get(t, 0) or 0))

        pos_type = "BUY" if order.type == mt5.ORDER_TYPE_BUY_LIMIT else "SELL"
        sig_e    = "🟢" if pos_type == "BUY" else "🔴"
        entry    = float(order.price_open)

        approach_state = _pending_trend_approach.get(ticket)

        # ─────────────────────────────────────────────────────────────────
        # ─ Round 1: ตรวจ approach ─────────────────────────────────────────
        # ─────────────────────────────────────────────────────────────────
        if approach_state is None:
            # คำนวณว่าราคาปัจจุบัน "เข้าใกล้" entry ไหม
            if pos_type == "BUY":
                _cur = float(tick.ask)
                approaching = _cur <= entry + _approach_dist
            else:
                _cur = float(tick.bid)
                approaching = _cur >= entry - _approach_dist

            if not approaching:
                continue

            # ── ข้อมูล swing พร้อมไหม ──
            if not _sdr(_tf):
                try:
                    from hhll_swing import fetch_hhll as _fhhll; _fhhll(_tf)
                except Exception:
                    pass
                if not _sdr(_tf):
                    continue

            _allowed, _why = _tas(_tf, pos_type)
            if _allowed and _why == "?":
                try:
                    from hhll_swing import fetch_hhll as _fhhll; _fhhll(_tf)
                except Exception:
                    pass
                _allowed, _why = _tas(_tf, pos_type)
                if _allowed and _why == "?":
                    continue

            _sh, _sl  = _ghl(_tf)
            _sh_price = float(_sh["price"]) if _sh else None
            _sl_price = float(_sl["price"]) if _sl else None
            _sh_time  = int(_sh["time"])  if _sh and "time" in _sh else 0
            _sl_time  = int(_sl["time"])  if _sl and "time" in _sl else 0
            _dist_pt  = round(abs(_cur - entry) / _pt)

            # เช็ค last_label + swing direction ใน round1
            # BUY block: LL (low < prev low) หรือ HL ที่กำลังลด (hl < prev_hl)
            # SELL block: HH (high > prev high) หรือ LH ที่กำลังสูงขึ้น (lh > prev_lh)
            _hhll_d_r1   = _ghd(_tf) or {}
            _last_lbl_r1 = _hhll_d_r1.get("last_label", "")
            if _allowed and _last_lbl_r1:
                _hl_r1      = _hhll_d_r1.get("hl") or {}
                _ll_r1      = _hhll_d_r1.get("ll") or {}
                _lh_r1      = _hhll_d_r1.get("lh") or {}
                _hh_r1      = _hhll_d_r1.get("hh") or {}
                _prev_hl_r1 = _hhll_d_r1.get("prev_hl") or {}
                _prev_lh_r1 = _hhll_d_r1.get("prev_lh") or {}
                if pos_type == "BUY":
                    if _last_lbl_r1 == "ll" and _ll_r1 and _hl_r1:
                        _allowed = False
                        _why = f"LL ({float(_ll_r1['price']):.2f} < {float(_hl_r1['price']):.2f})"
                    elif _last_lbl_r1 == "hl" and _hl_r1 and _prev_hl_r1:
                        if float(_hl_r1["price"]) < float(_prev_hl_r1["price"]):
                            _allowed = False
                            _why = f"HL ต่ำลง ({float(_hl_r1['price']):.2f} < {float(_prev_hl_r1['price']):.2f})"
                    elif _last_lbl_r1 == "lh" and _lh_r1 and _hh_r1:
                        _allowed = False
                        _why = f"LH ({float(_lh_r1['price']):.2f} < {float(_hh_r1['price']):.2f})"
                elif pos_type == "SELL":
                    if _last_lbl_r1 == "hh" and _hh_r1 and _lh_r1:
                        _allowed = False
                        _why = f"HH ({float(_hh_r1['price']):.2f} > {float(_lh_r1['price']):.2f})"
                    elif _last_lbl_r1 == "lh" and _lh_r1 and _prev_lh_r1:
                        if float(_lh_r1["price"]) > float(_prev_lh_r1["price"]):
                            _allowed = False
                            _why = f"LH สูงขึ้น ({float(_lh_r1['price']):.2f} > {float(_prev_lh_r1['price']):.2f})"
                    elif _last_lbl_r1 == "hl" and _hl_r1 and _ll_r1:
                        _allowed = False
                        _why = f"HL ({float(_hl_r1['price']):.2f} > {float(_ll_r1['price']):.2f})"

            log_event("PENDING_TREND_CHECK", "round1",
                      ticket=ticket, tf=_tf, signal=pos_type,
                      allowed=_allowed, why=_why, dist_pt=_dist_pt, entry=entry)

            if not _allowed:
                # ── FAIL: ยกเลิก pending order ──
                _info = pending_order_tf.get(ticket)
                _ot   = _pending_order_type_name(order)
                r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": ticket})
                if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                    pending_order_tf.pop(ticket, None)
                    log_event(
                        "ORDER_CANCELED",
                        f"Pending Trend Check [round1]: trend={_why}",
                        ticket=ticket, tf=_tf,
                        side=pos_type, order_type=_ot, entry=entry,
                        flow_id=_info.get("flow_id", "") if isinstance(_info, dict) else "",
                        dist_pt=_dist_pt,
                    )
                    await tg(app, (
                        f"🚫 *Pending Trend Check: ยกเลิก [round1]*\n"
                        f"{sig_e} {_ot} `#{ticket}` [{_tf}]\n"
                        f"Trend สวนทาง: `{_why}`\n"
                        f"ราคาใกล้ entry {entry:.2f} ({_dist_pt}pt)"
                    ))
                    _pending_trend_approach.pop(ticket, None)
            else:
                # ── PASS: บันทึก swing baseline รอ round 2 ──
                _hhll_d  = _hhll_d_r1  # reuse จาก round1 check ด้านบน
                _lbl     = _hhll_d.get("last_label", "")
                _piv     = _hhll_d.get(_lbl.lower()) if _lbl else None
                _piv_t   = int(_piv["time"]) if _piv and "time" in _piv else 0
                _tf_secs = int(TF_SECONDS_MAP.get(_tf, 300) or 300)
                _hhll_rb = int(getattr(_hs, "HHLL_RIGHT", 5))
                _r2_start = (_piv_t + _hhll_rb * _tf_secs) if _piv_t else (int(_time.time()) + _hhll_rb * _tf_secs)

                _pending_trend_approach[ticket] = {
                    "tf": _tf,
                    "signal": pos_type,
                    "round1_sh": _sh_price,
                    "round1_sl": _sl_price,
                    "round1_sh_t": _sh_time,
                    "round1_sl_t": _sl_time,
                    "round2_start_time": _r2_start,
                }
                log_event("PENDING_TREND_CHECK", "round1_pass",
                          ticket=ticket, tf=_tf, signal=pos_type,
                          sh=_sh_price, sl=_sl_price,
                          sh_t=_sh_time, sl_t=_sl_time,
                          dist_pt=_dist_pt)
                await tg(app, (
                    f"✅ *Pending Trend Check: ผ่าน [round1]*\n"
                    f"{sig_e} {_pending_order_type_name(order)} `#{ticket}` [{_tf}]\n"
                    f"Trend: `{_why}` | ใกล้ entry {_dist_pt}pt\n"
                    f"รอ Swing ใหม่ → Round 2"
                ))

        # ─────────────────────────────────────────────────────────────────
        # ─ Round 2: รอ swing ใหม่ (ยัง pending อยู่) ─────────────────────
        # ─────────────────────────────────────────────────────────────────
        else:
            # ถ้า config กำหนดแค่ 1 รอบ → ข้ามไปโดยไม่ลบ state
            # (state ต้องอยู่รอ fill → fill_round1_skip_approach_passed)
            # ❌ เดิม: pop() ลบ state ทำให้ Round 1 วิ่งซ้ำทุก 2 cycle
            if int(getattr(config, "PENDING_TREND_CHECK_ROUNDS", 1)) < 2:
                continue

            if _time.time() < approach_state.get("round2_start_time", 0):
                continue

            _sh, _sl = _ghl(_tf)
            _new_h   = float(_sh["price"]) if _sh else None
            _new_l   = float(_sl["price"]) if _sl else None
            _r1_h    = approach_state.get("round1_sh")
            _r1_l    = approach_state.get("round1_sl")
            _h_chg   = (_new_h is not None and _r1_h is not None and abs(_new_h - _r1_h) > 0.01)
            _l_chg   = (_new_l is not None and _r1_l is not None and abs(_new_l - _r1_l) > 0.01)

            if not (_h_chg or _l_chg):
                continue  # swing ยังไม่เปลี่ยน

            _allowed, _why = _tas(_tf, pos_type)
            if _allowed and _why == "?":
                continue

            # เช็คทิศทาง swing (ทุก trend mode) เทียบกับ baseline ของ round1
            # BUY block: LL (new_l < r1_l) หรือ LH (new_h < r1_h → resistance ลด)
            # SELL block: HH (new_h > r1_h) หรือ HL (new_l > r1_l → support ขึ้น)
            if _allowed:
                if pos_type == "BUY":
                    if _l_chg and _new_l < _r1_l:
                        _allowed = False
                        _why = f"LL ({_new_l:.2f} < {_r1_l:.2f})"
                    elif _h_chg and _new_h < _r1_h:
                        _allowed = False
                        _why = f"LH ({_new_h:.2f} < {_r1_h:.2f})"
                elif pos_type == "SELL":
                    if _h_chg and _new_h > _r1_h:
                        _allowed = False
                        _why = f"HH ({_new_h:.2f} > {_r1_h:.2f})"
                    elif _l_chg and _new_l > _r1_l:
                        _allowed = False
                        _why = f"HL ({_new_l:.2f} > {_r1_l:.2f})"

            _changed = "/".join(p for p in ["H" if _h_chg else "", "L" if _l_chg else ""] if p)
            log_event("PENDING_TREND_CHECK", "round2",
                      ticket=ticket, tf=_tf, signal=pos_type,
                      allowed=_allowed, why=_why, swing_changed=_changed)

            if not _allowed:
                _info = pending_order_tf.get(ticket)
                _ot   = _pending_order_type_name(order)
                r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": ticket})
                if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                    pending_order_tf.pop(ticket, None)
                    log_event(
                        "ORDER_CANCELED",
                        f"Pending Trend Check [round2]: swing={_changed}, block={_why}",
                        ticket=ticket, tf=_tf,
                        side=pos_type, order_type=_ot, entry=entry,
                        flow_id=_info.get("flow_id", "") if isinstance(_info, dict) else "",
                    )
                    await tg(app, (
                        f"🚫 *Pending Trend Check: ยกเลิก [round2]*\n"
                        f"{sig_e} {_ot} `#{ticket}` [{_tf}]\n"
                        f"Swing เปลี่ยน ({_changed}) → `{_why}`"
                    ))
                _pending_trend_approach.pop(ticket, None)
            else:
                # Round 2 ผ่าน → clear state
                log_event("PENDING_TREND_CHECK", "round2_pass",
                          ticket=ticket, tf=_tf, signal=pos_type, swing_changed=_changed)
                _pending_trend_approach.pop(ticket, None)


# -------------------------------------------------------------
async def check_fill_pdfiboplus(app):
    """
    PD Zone Fill Check — เช็ค position ที่เพิ่ง fill ว่าอยู่ใน zone ที่ถูกต้องไหม
    Gate: PDFIBOPLUS_ENABLED
    Skip: S9 (RSI Divergence)

    รอบ 1 (fill_check) : เช็คทันทีหลัง fill — ถ้า FAIL ปิด position
                         ถ้า PASS → บันทึก H/L รอ round 2
    รอบ 2              : เช็คเมื่อ H/L เปลี่ยน — entry อาจเลื่อนเข้า Premium/Discount ผิดฝั่ง
    """
    if not getattr(config, "PDFIBOPLUS_ENABLED", False):
        return
    positions = mt5.positions_get(symbol=SYMBOL)
    if positions is None:
        return  # MT5 error — ไม่ clear state
    if not positions:
        _pdfiboplus_fill_state.clear()
        _pdfiboplus_fill_checked.clear()
        return

    open_pos_tickets = {p.ticket for p in positions}
    for _t in list(_pdfiboplus_fill_state.keys()):
        if _t not in open_pos_tickets:
            _pdfiboplus_fill_state.pop(_t, None)
    _pdfiboplus_fill_checked.difference_update(
        _t for _t in list(_pdfiboplus_fill_checked) if _t not in open_pos_tickets
    )

    from hhll_swing import get_swing_hl_pts as _gshl

    for pos in positions:
        ticket = pos.ticket
        if ticket in _pdfiboplus_fill_checked:
            continue
        sid = position_sid.get(ticket)
        # Skip standalone strategies
        if sid in (10, 12, 13, 15, 16, 17, 18, 19, 20, 20.5, 20.6, 20.7):
            continue  # S1/S2/S3/S11 ไม่ใช้ PD Fibo Plus | S9/S10/S13/S14/S15/S16/S17/S18/S19 skip

        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        sig_e    = "🟢" if pos_type == "BUY" else "🔴"
        fvg_info = fvg_order_tickets.get(ticket)

        # Resolve TF (3-tier fallback)
        _pz_tf = position_tf.get(ticket)
        if not _pz_tf and fvg_info:
            _pz_tf = fvg_info.get("tf")
        if not _pz_tf:
            _pend_info = pending_order_tf.get(ticket)
            if isinstance(_pend_info, dict):
                _pz_tf = _pend_info.get("tf")
        if not _pz_tf:
            _c_tf, _, _ = _infer_position_meta_from_comment(pos)
            if _c_tf:
                _pz_tf = _c_tf
                position_tf[ticket] = _c_tf
        if not _pz_tf:
            _pz_tf = "M1"

        # Multi-TF เช่น "[M15_M30]" หรือ "M15+M30" → เลือก TF เล็กสุด
        # (PD Zone ใช้ HHLL ของ TF เดี่ยว — TF เล็กสุดให้ zone ที่ tight และ responsive ที่สุด)
        _TF_ORDER = ["M1", "M5", "M15", "M30", "H1", "H4", "H12", "D1", "W1", "MN1"]
        if any(sep in str(_pz_tf) for sep in ["_", "+", ","]):
            import re as _re_pz
            _parts = _re_pz.findall(r'[A-Z]\d+', str(_pz_tf))
            if _parts:
                _pz_tf = min(_parts, key=lambda t: _TF_ORDER.index(t) if t in _TF_ORDER else 99)

        _pz_gap_bot = float((fvg_info or {}).get("gap_bot", 0) or 0)
        _pz_gap_top = float((fvg_info or {}).get("gap_top", 0) or 0)

        fs = _pdfiboplus_fill_state.get(ticket)

        # ── Pending close retry ─────────────────────────────────────────
        if fs and fs.get("pending_close"):
            ok, cp = _close_position(pos, pos_type, "PD Zone fill_round2 retry")
            log_event("PDFIBOPLUS", "fill_close_round2_retry",
                      ticket=ticket, signal=pos_type, tf=_pz_tf, ok=ok)
            if ok:
                _entry_state[ticket] = "done"
                fvg_order_tickets.pop(ticket, None)
                save_runtime_state()
                _pz_eq = round((fs["fill_h"] + fs["fill_l"]) / 2, 2)
                log_event("PDFIBOPLUS", "fill_close_round2",
                          ticket=ticket, signal=pos_type, tf=_pz_tf, close_price=cp)
                _zone_label = "Discount 🟢" if pos_type == "SELL" else "Premium 🔴"
                await tg(app, (
                    f"🛡️ *PD Fibo Plus: ปิด Position [round2] (retry)*\n"
                    f"{sig_e} Ticket:`{ticket}` [{_pz_tf}]\n"
                    f"Entry อยู่ใน {_zone_label} (ผิดฝั่ง)\n"
                    f"ปิดที่: `{cp:.2f}`"
                ))
                _pdfiboplus_fill_state.pop(ticket, None)
                _pdfiboplus_fill_checked.add(ticket)
            continue

        # ── Round 2: H/L เปลี่ยน → re-check zone ──────────────────────
        if fs is not None:
            try:
                _sh2, _sl2 = _gshl(_pz_tf)
                _new_h = float(_sh2["price"]) if _sh2 else 0.0
                _new_l = float(_sl2["price"]) if _sl2 else 0.0
            except Exception:
                _new_h = _new_l = 0.0
            _h_chg = abs(_new_h - fs["fill_h"]) > 0.01
            _l_chg = abs(_new_l - fs["fill_l"]) > 0.01
            if not (_h_chg or _l_chg):
                continue  # H/L ยังไม่เปลี่ยน รอ cycle ถัดไป
            if not (_new_h > _new_l > 0):
                continue
            _r2_result = _pdfiboplus_in_zone(
                float(pos.price_open), pos_type, _new_h, _new_l,
                sid=sid, gap_bot=_pz_gap_bot, gap_top=_pz_gap_top
            )
            _r2_eq      = round((_new_h + _new_l) / 2, 2)
            _r2_changed = "/".join(p for p in ["H" if _h_chg else "", "L" if _l_chg else ""] if p)
            log_event("PDFIBOPLUS", "fill_round2",
                      ticket=ticket, signal=pos_type, tf=_pz_tf,
                      price=pos.price_open, h=_new_h, l=_new_l,
                      eq=_r2_eq, changed=_r2_changed,
                      result="PASS" if _r2_result else "FAIL")
            if not _r2_result:
                ok, cp = _close_position(pos, pos_type, "PD Zone fill round2 failed")
                if ok:
                    _entry_state[ticket] = "done"
                    fvg_order_tickets.pop(ticket, None)
                    save_runtime_state()
                    log_event("PDFIBOPLUS", "fill_close_round2",
                              ticket=ticket, signal=pos_type, tf=_pz_tf,
                              price=pos.price_open, eq=_r2_eq, close_price=cp)
                    _zone_label = "Discount 🟢" if pos_type == "SELL" else "Premium 🔴"
                    await tg(app, (
                        f"🛡️ *PD Fibo Plus: ปิด Position [round2]*\n"
                        f"{sig_e} Ticket:`{ticket}` [{_pz_tf}]\n"
                        f"H/L เปลี่ยน ({_r2_changed}) → Entry เข้า {_zone_label} (ผิดฝั่ง)\n"
                        f"Entry: `{pos.price_open}` | EQ: `{_r2_eq}`\n"
                        f"H: `{_new_h}` | L: `{_new_l}`\n"
                        f"ปิดที่: `{cp:.2f}`"
                    ))
                    _pdfiboplus_fill_state.pop(ticket, None)
                    _pdfiboplus_fill_checked.add(ticket)
                else:
                    log_event("PDFIBOPLUS", "fill_close_round2_failed",
                              ticket=ticket, signal=pos_type, tf=_pz_tf)
                    await tg(app, (
                        f"⚠️ *PD Fibo Plus: ปิด Position ล้มเหลว [round2]*\n"
                        f"{sig_e} Ticket:`{ticket}` [{_pz_tf}]\n"
                        f"H/L เปลี่ยน ({_r2_changed}) → Entry ผิดฝั่ง — จะ retry ทุกรอบสแกน"
                    ))
                    fs["pending_close"] = True
                    _pdfiboplus_fill_state[ticket] = fs
            else:
                # round 2 ผ่าน — zone ยังถูกต้อง
                _pdfiboplus_fill_state.pop(ticket, None)
                _pdfiboplus_fill_checked.add(ticket)
                log_event("PDFIBOPLUS", "fill_round2_pass",
                          ticket=ticket, signal=pos_type, tf=_pz_tf,
                          h=_new_h, l=_new_l, eq=_r2_eq, changed=_r2_changed)
            continue

        # ── Round 1: fill_check (ครั้งแรกหลัง fill) ────────────────────
        try:
            _sh_pt, _sl_pt = _gshl(_pz_tf)
            _pz_h = float(_sh_pt["price"]) if _sh_pt else 0.0
            _pz_l = float(_sl_pt["price"]) if _sl_pt else 0.0
        except Exception:
            _pz_h = _pz_l = 0.0

        if not (_pz_h > _pz_l > 0):
            # ข้อมูล HHLL ยังไม่พร้อม → force fetch ตรงแทนรอ scanner
            try:
                from hhll_swing import fetch_hhll as _fhhll_pz
                _fhhll_pz(_pz_tf)
                _sh_pt, _sl_pt = _gshl(_pz_tf)
                _pz_h = float(_sh_pt["price"]) if _sh_pt else 0.0
                _pz_l = float(_sl_pt["price"]) if _sl_pt else 0.0
            except Exception:
                pass
            if not (_pz_h > _pz_l > 0):
                log_event("PDFIBOPLUS", "fill_round1_skip_no_data",
                          ticket=ticket, signal=pos_type, tf=_pz_tf)
                continue

        _pz_result = _pdfiboplus_in_zone(
            float(pos.price_open), pos_type, _pz_h, _pz_l,
            sid=sid, gap_bot=_pz_gap_bot, gap_top=_pz_gap_top
        )
        _pz_eq = round((_pz_h + _pz_l) / 2, 2)
        log_event("PDFIBOPLUS", "fill_check",
                  ticket=ticket, signal=pos_type, tf=_pz_tf,
                  price=pos.price_open, h=_pz_h, l=_pz_l,
                  eq=_pz_eq, result="PASS" if _pz_result else "FAIL",
                  sid=sid)
        if not _pz_result:
            ok, cp = _close_position(pos, pos_type, "PD Zone fill check failed")
            if ok:
                _entry_state[ticket] = "done"
                fvg_order_tickets.pop(ticket, None)
                save_runtime_state()
                log_event("PDFIBOPLUS", "fill_close",
                          ticket=ticket, signal=pos_type, tf=_pz_tf,
                          price=pos.price_open, eq=_pz_eq, close_price=cp)
                _zone_label = "Discount 🟢" if pos_type == "SELL" else "Premium 🔴"
                await tg(app, (
                    f"🛡️ *PD Fibo Plus: ปิด Position ที่ fill ผิด Zone*\n"
                    f"{sig_e} Ticket:`{ticket}` [{_pz_tf}]\n"
                    f"Entry อยู่ใน {_zone_label} (ผิดฝั่ง)\n"
                    f"Entry: `{pos.price_open}` | EQ: `{_pz_eq}`\n"
                    f"H: `{_pz_h}` | L: `{_pz_l}`"
                ))
                _pdfiboplus_fill_checked.add(ticket)
            else:
                # close ล้มเหลว → retry ทุก cycle (ห้าม add _pdfiboplus_fill_checked)
                log_event("PDFIBOPLUS", "fill_close_failed",
                          ticket=ticket, signal=pos_type, tf=_pz_tf,
                          price=pos.price_open, eq=_pz_eq)
                await tg(app, (
                    f"⚠️ *PD Fibo Plus: ปิด Position ล้มเหลว [round1]*\n"
                    f"{sig_e} Ticket:`{ticket}` [{_pz_tf}]\n"
                    f"Entry ผิดฝั่ง — จะ retry ทุกรอบสแกน"
                ))
                _pdfiboplus_fill_state[ticket] = {
                    "tf":          _pz_tf,
                    "signal":      pos_type,
                    "fill_h":      _pz_h,
                    "fill_l":      _pz_l,
                    "gap_bot":     _pz_gap_bot,
                    "gap_top":     _pz_gap_top,
                    "pending_close": True,
                }
        else:
            # Round 1 PASS → ตรวจ S14 strong counter-trend ก่อน round 2
            # S14 Sweep RSI bypass fill_trend_recheck โดย design แต่ถ้า trend strong
            # ขัดทิศ (bull_strong สำหรับ SELL / bear_strong สำหรับ BUY) → ปิดทันที
            # แทนรอ round2 (ซึ่งอาจล่าช้า 1+ นาทีกว่า swing จะเปลี่ยน)
            if sid == 14:
                _stored_tf = position_trend_filter.get(ticket, "")
                _s14_strong_counter = (
                    (pos_type == "SELL" and "bull" in _stored_tf.lower() and "strong" in _stored_tf.lower()) or
                    (pos_type == "BUY"  and "bear" in _stored_tf.lower() and "strong" in _stored_tf.lower())
                )
                if _s14_strong_counter:
                    log_event("PDFIBOPLUS", "fill_round1_s14_strong_counter",
                              ticket=ticket, signal=pos_type, tf=_pz_tf,
                              trend_filter=_stored_tf, eq=_pz_eq)
                    ok, cp = _close_position(pos, pos_type, "S14 strong-counter fill")
                    if ok:
                        _entry_state[ticket] = "done"
                        fvg_order_tickets.pop(ticket, None)
                        save_runtime_state()
                        log_event("PDFIBOPLUS", "fill_close_s14_strong_counter",
                                  ticket=ticket, signal=pos_type, tf=_pz_tf,
                                  trend_filter=_stored_tf, close_price=cp)
                        await tg(app, (
                            f"⚡ *S14: ปิดทันที — trend strong ขัดทิศ*\n"
                            f"{sig_e} Ticket:`{ticket}` [{_pz_tf}]\n"
                            f"Trend: `{_stored_tf}` | Entry: `{pos.price_open}` | ปิดที่: `{cp:.2f}`"
                        ))
                        # สำเร็จ → mark checked (จบงาน)
                        _pdfiboplus_fill_checked.add(ticket)
                    else:
                        # close ล้มเหลว → ตั้ง pending_close=True ให้ retry รอบถัดไป
                        # ห้าม add เข้า _pdfiboplus_fill_checked ไม่งั้นจะถูก skip ก่อนถึง retry block
                        log_event("PDFIBOPLUS", "fill_s14_strong_counter_close_fail",
                                  ticket=ticket, signal=pos_type, tf=_pz_tf)
                        _pdfiboplus_fill_state[ticket] = {
                            "tf": _pz_tf, "signal": pos_type,
                            "fill_h": _pz_h, "fill_l": _pz_l,
                            "gap_bot": _pz_gap_bot, "gap_top": _pz_gap_top,
                            "pending_close": True,   # retry ทันที
                        }
                    continue

            # Round 1 PASS → บันทึก H/L รอ round 2
            _pdfiboplus_fill_state[ticket] = {
                "tf":        _pz_tf,
                "signal":    pos_type,
                "fill_h":    _pz_h,
                "fill_l":    _pz_l,
                "gap_bot":   _pz_gap_bot,
                "gap_top":   _pz_gap_top,
                "pending_close": False,
            }
            log_event("PDFIBOPLUS", "fill_round1_pass_wait_hl",
                      ticket=ticket, signal=pos_type, tf=_pz_tf,
                      h=_pz_h, l=_pz_l, eq=_pz_eq)


# -------------------------------------------------------------
async def check_entry_candle_quality(app):
    """
    Check the entry candle for all strategies.

    BUY entry candle:
      green body >= 35%  -> done
      green body < 35%   -> waiting_next
      red any body       -> waiting_bad: SL=swing_low-1.0, TP=entry.open

    SELL entry candle:
      red body >= 35%    -> done
      red body < 35%     -> waiting_next
      green any body     -> waiting_bad: SL=swing_high+1.0, TP=entry.open

    waiting_bad on the next closed candle:
      BUY:  close>=entry -> close position | close<entry -> SL=next.low-1.0, TP=next.open -> done
      SELL: close<=entry -> close position | close>entry -> SL=next.high+1.0, TP=next.open -> done
    """
    global _last_meta_map_key
    if not getattr(config, "ENTRY_CANDLE_ENABLED", True):
        return
    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        _entry_state.clear()
        _entry_bar_none_first.clear()
        return
    open_pos_tickets = {p.ticket for p in positions}
    open_order_tickets = {o.ticket for o in (mt5.orders_get(symbol=SYMBOL) or [])}
    for t in list(_s8_fill_sl.keys()):
        if t not in open_pos_tickets and t not in open_order_tickets:
            _s8_fill_sl.pop(t, None)

    # หมายเหตุ: first-run guard ของ _fill_initialized ย้ายไป check_limit_fill_notify() แล้ว

    now = now_bkk().strftime("%H:%M:%S")
    open_tickets = {p.ticket for p in positions}
    for t in list(_entry_bar_none_first.keys()):
        if t not in open_tickets:
            _entry_bar_none_first.pop(t, None)

    # Entry Candle Focus Opposite (frozen_side marker)
    # Same side as marker -> skip ECM
    # Opposite side -> ECM works only when gate passes
    entry_focus_skip_tickets: set[int] = set()
    if getattr(config, "ENTRY_CANDLE_FOCUS_NEW_ENABLED", False):
        pending_efn = mt5.orders_get(symbol=SYMBOL) or []
        frozen_side_ec = _focus_update_frozen_side("entry_candle", positions, pending_efn)
        if frozen_side_ec is not None:
            for p in positions:
                p_side = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
                if p_side == frozen_side_ec:
                    entry_focus_skip_tickets.add(p.ticket)
                elif not _focus_gate_passed(
                    "entry_candle", frozen_side_ec, positions, position_tf.get(p.ticket)
                ):
                    entry_focus_skip_tickets.add(p.ticket)

    for pos in positions:
        ticket   = pos.ticket
        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        sid      = position_sid.get(ticket)
        if sid in (10, 12, 13, 15, 16, 17, 18, 19, 20, 20.5, 20.6, 20.7):
            continue  # standalone strategies (S15 = VP absorption, มี entry logic เอง; S18 = TJR; S19 = ICT SB)
        sig_e    = "🟢" if pos_type == "BUY" else "🔴"
        state    = _entry_state.get(ticket)
        if _trade_debug_enabled():
            print(f"[{now}] entry_check: {pos_type} {ticket} state={state} fvg={bool(fvg_order_tickets.get(ticket))} pos_tf={position_tf.get(ticket)}")

        # ── Limit Fill notify ย้ายไป check_limit_fill_notify() แล้ว (อิสระจาก ENTRY_CANDLE_ENABLED) ──
        fvg_info = fvg_order_tickets.get(ticket)
        pattern_name = position_pattern.get(ticket, "") or ""

        # ── RSI Fill Recheck ย้ายไป check_fill_rsi_recheck() แล้ว ──
        # (อิสระจาก ENTRY_CANDLE_ENABLED — ถ้า RSI fail position จะถูกปิดก่อนถึงตรงนี้)

        if ticket in entry_focus_skip_tickets:
            continue

        if state == "done":
            fvg_order_tickets.pop(ticket, None)
            save_runtime_state()
            continue

        if pos.sl == 0 and ticket in _s8_fill_sl:
            intended_sl = float(_s8_fill_sl.get(ticket, 0) or 0)
            if intended_sl > 0:
                _arm_fill = False
                _arm_fill_reason = ""
                _pos_sid = position_sid.get(ticket)
                if config.DELAY_SL_MODE == "off":
                    # Original S8 fallback or disabled mode -> arm immediately
                    _arm_fill = True
                    _arm_fill_reason = "fill fallback"
                elif config.DELAY_SL_MODE == "time":
                    import time as _time
                    _now_ts = int(_time.time())
                    _pos_tf = position_tf.get(ticket, "M1")
                    _tf_val_fill = TF_OPTIONS.get(_pos_tf, mt5.TIMEFRAME_M1)
                    _tf_secs_fill = _get_tf_seconds(_tf_val_fill)
                    _threshold_fill = _tf_secs_fill * 0.10
                    _rates_fill = mt5.copy_rates_from_pos(SYMBOL, _tf_val_fill, 1, 3)
                    if _rates_fill is not None and len(_rates_fill) > 0:
                        _candle_end_fill = int(_rates_fill[-1]["time"]) + _tf_secs_fill
                        _time_left_fill = _candle_end_fill - _now_ts
                        if _time_left_fill <= _threshold_fill:
                            _arm_fill = True
                            _arm_fill_reason = f"time เหลือ {_time_left_fill}s"
                elif config.DELAY_SL_MODE == "price":
                    _tick_fill = mt5.symbol_info_tick(SYMBOL)
                    if _tick_fill:
                        _spread_fill = abs(float(_tick_fill.ask) - float(_tick_fill.bid))
                        if pos_type == "BUY" and float(_tick_fill.ask) > pos.price_open + _spread_fill:
                            _arm_fill = True
                            _arm_fill_reason = f"ask {float(_tick_fill.ask):.2f} > entry+spread"
                        elif pos_type == "SELL" and float(_tick_fill.bid) < pos.price_open - _spread_fill:
                            _arm_fill = True
                            _arm_fill_reason = f"bid {float(_tick_fill.bid):.2f} < entry-spread"

                if _arm_fill:
                    ok_s8 = _modify_sl(pos, intended_sl)
                    if ok_s8:
                        log_event(
                            "SL_CHANGED",
                            "delay_sl_fill_arm",
                            ticket=ticket,
                            side=pos_type,
                            tf=position_tf.get(ticket, fvg_info.get("tf", "M1") if fvg_info else "M1"),
                            old_sl=0.0,
                            new_sl=float(intended_sl),
                            old_tp=float(pos.tp),
                            new_tp=float(pos.tp),
                        )
                        await tg(app, (
                            f"🛡️ *ตั้ง SL หลัง Fill*\n"
                            f"{sig_e} Ticket:`{ticket}`\n"
                            f"🛑 SL: `0.00` -> `{intended_sl:.2f}`\n"
                            f"เหตุผล: {_arm_fill_reason}"
                        ))
                        _s8_fill_sl.pop(ticket, None)
                    else:
                        print(f"⚠️ [{now}] fill arm SL failed ticket={ticket} sl={intended_sl:.2f} -> retry next cycle")

        # If bot restarted and position already has solid profit (>= 5 USD),
        # treat entry candle flow as already done.
        if state is None and pos.profit >= 5.0:
            _entry_state[ticket] = "done"
            fvg_order_tickets.pop(ticket, None)
            save_runtime_state()
            print(f"ℹ️ [{now}] {pos_type} {ticket} profit={pos.profit:.2f} -> auto done")
            continue

        # Get TF from position_tf (all strategies) or fvg_order_tickets (FVG)
        pos_tf   = position_tf.get(ticket)
        meta_source = "in_memory" if pos_tf else None

        # Try infer TF/SID from comment first; it is more reliable than price matching.
        matched_pending_ticket = None
        matched_pending_info = None
        for _pticket, _pinfo in list(pending_order_tf.items()):
            if not isinstance(_pinfo, dict):
                continue
            _pgap_bot = _pinfo.get("gap_bot", 0)
            _pgap_top = _pinfo.get("gap_top", 0)
            if _pgap_bot <= pos.price_open <= _pgap_top or \
               abs(pos.price_open - _pgap_bot) < 2 or \
               abs(pos.price_open - _pgap_top) < 2:
                matched_pending_ticket = _pticket
                matched_pending_info = _pinfo
                break

        if not pos_tf and not fvg_info:
            c_tf, c_sid, c_source = _infer_position_meta_from_comment(pos)
            if c_tf:
                position_tf[ticket] = c_tf
                pos_tf = c_tf
                meta_source = c_source
            if ticket not in position_sid and c_sid is not None:
                position_sid[ticket] = c_sid

        # If a new position still has no position_tf, fallback from pending_order_tf by nearby entry price.
        if not pos_tf and not fvg_info:
            for pticket, pinfo in list(pending_order_tf.items()):
                if isinstance(pinfo, dict):
                    # pending order whose price is close to this position entry
                    pgap_bot = pinfo.get("gap_bot", 0)
                    pgap_top = pinfo.get("gap_top", 0)
                    if pgap_bot <= pos.price_open <= pgap_top or \
                       abs(pos.price_open - pgap_bot) < 2 or \
                       abs(pos.price_open - pgap_top) < 2:
                        position_tf[ticket]  = pinfo.get("tf", "M1")
                        if ticket not in position_sid:
                            position_sid[ticket] = pinfo.get("sid", 0)
                        if ticket not in position_pattern and pinfo.get("pattern"):
                            position_pattern[ticket] = pinfo.get("pattern", "")
                        if ticket not in position_trend_filter and pinfo.get("trend_filter"):
                            position_trend_filter[ticket] = pinfo.get("trend_filter", "")
                        if ticket not in position_zone_meta and pinfo.get("s1_zone_meta"):
                            position_zone_meta[ticket] = dict(pinfo.get("s1_zone_meta") or {})
                        if ticket not in position_forward_meta and pinfo.get("s1_forward_meta"):
                            position_forward_meta[ticket] = dict(pinfo.get("s1_forward_meta") or {})
                        pos_tf = position_tf[ticket]
                        meta_source = f"pending_price_match:{pticket}"
                        break

        if matched_pending_ticket and matched_pending_info:
            if ticket not in position_sid:
                position_sid[ticket] = matched_pending_info.get("sid", 0)
            if ticket not in position_pattern and matched_pending_info.get("pattern"):
                position_pattern[ticket] = matched_pending_info.get("pattern", "")
            if ticket not in position_trend_filter and matched_pending_info.get("trend_filter"):
                position_trend_filter[ticket] = matched_pending_info.get("trend_filter", "")
            if ticket not in position_zone_meta and matched_pending_info.get("s1_zone_meta"):
                position_zone_meta[ticket] = dict(matched_pending_info.get("s1_zone_meta") or {})
            if ticket not in position_forward_meta and matched_pending_info.get("s1_forward_meta"):
                position_forward_meta[ticket] = dict(matched_pending_info.get("s1_forward_meta") or {})
            await _cancel_s10_sibling_orders(app, ticket, matched_pending_info, matched_pending_ticket)

        if fvg_info:
            if ticket not in position_zone_meta and fvg_info.get("s1_zone_meta"):
                position_zone_meta[ticket] = dict(fvg_info.get("s1_zone_meta") or {})
            if ticket not in position_forward_meta and fvg_info.get("s1_forward_meta"):
                position_forward_meta[ticket] = dict(fvg_info.get("s1_forward_meta") or {})

        debug_tf = fvg_info.get("tf", "M1") if fvg_info else position_tf.get(ticket, pos_tf or "?")
        debug_sid = position_sid.get(ticket)
        debug_source = "fvg_memory" if fvg_info else (meta_source or "unknown")
        if _trade_debug_enabled():
            meta_key = f"{ticket}|{debug_tf}|{debug_sid}|{debug_source}"
            if meta_key != _last_meta_map_key:
                print(f"[{now}] meta_map: ticket={ticket} tf={debug_tf} sid={debug_sid} source={debug_source}")
                _last_meta_map_key = meta_key

        if fvg_info:
            tf_val = TF_OPTIONS.get(fvg_info.get("tf","M1"), mt5.TIMEFRAME_M1)
        elif pos_tf:
            tf_val = TF_OPTIONS.get(pos_tf, mt5.TIMEFRAME_M1)
        else:
            tf_val = mt5.TIMEFRAME_M1

        entry_bar, next_bar = _get_closed_bar(pos, tf_val)
        if entry_bar is None:
            tf_seconds = _get_tf_seconds(tf_val)
            expected_entry_close = ((int(pos.time) // tf_seconds) + 1) * tf_seconds
            now_ts = int(datetime.now().timestamp())
            warn_after = expected_entry_close + 60
            first_warn_ts = _entry_bar_none_first.get(ticket)
            if first_warn_ts is None:
                _entry_bar_none_first[ticket] = now_ts
            if now_ts >= warn_after and first_warn_ts is None:
                await tg(app, (f"⚠️ *entry_bar=None นาน >60s*\n"
                               f"{sig_e} Ticket:`{ticket}` pos.time=`{int(pos.time)}`\n"
                               f"fill={fmt_mt5_bkk_ts(int(pos.time), '%H:%M:%S')} tf={position_tf.get(ticket,'?')}"))
            continue
        _entry_bar_none_first.pop(ticket, None)

        # Notify entry candle close with OHLC + body%
        if ticket not in _entry_bar_notified:
            _entry_bar_notified[ticket] = True
            _o = float(entry_bar["open"]);  _h = float(entry_bar["high"])
            _l = float(entry_bar["low"]);   _c = float(entry_bar["close"])
            _rng  = _h - _l
            _body = abs(_c - _o)
            _body_pct = round(_body / _rng * 100 if _rng > 0 else 0)
            _bull = _c > _o
            _clr  = "🟢" if _bull else "🔴"
            _tf_name = position_tf.get(ticket, fvg_info.get("tf","M1") if fvg_info else "M1")
            _entry_close_time = _fmt_bkk_ts(int(entry_bar["time"]) + _get_tf_seconds(tf_val))
            log_event(
                "ENTRY_CANDLE",
                "Entry candle closed",
                ticket=ticket,
                side=pos_type,
                tf=_tf_name,
                open=f"{_o:.2f}",
                high=f"{_h:.2f}",
                low=f"{_l:.2f}",
                close=f"{_c:.2f}",
                body_pct=_body_pct,
                candle_close=_entry_close_time,
            )
            await tg(app, (f"🕯️ *แท่ง Entry จบ - {pos_type}{reverse_tag}*\n"
                          f"{sig_e} Ticket:`{ticket}` `{_tf_name}`\n"
                          f"📝 Pattern: `{pattern_name or '-'}`\n"
                          f"{_clr} O:`{_o:.2f}` H:`{_h:.2f}` L:`{_l:.2f}` C:`{_c:.2f}`\n"
                          f"📊 Body: `{_body_pct}%`\n"
                          f"🕐 Candle Close: `{_entry_close_time}`"))
            print(f"[{now}] {pos_type} {ticket} entry bar closed body={_body_pct}%")

        def bar_info(bar):
            o = float(bar["open"]); h = float(bar["high"])
            l = float(bar["low"]);  c = float(bar["close"])
            rng = h - l
            return c > o, abs(c-o)/rng if rng > 0 else 0, round(abs(c-o)/rng*100 if rng > 0 else 0)

        spread_price = _get_spread_price()
        current_price = float(entry_bar["close"])

        if state is None:
            # ── PD Fibo Plus fill check ย้ายไป check_fill_pdfiboplus() แล้ว ──

            # Evaluate the entry candle
            bull, body_pct, body_pct_int = bar_info(entry_bar)

            # Find prev_bar (the candle before entry_bar)
            entry_idx = None
            _rates_25 = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, 25)
            _rates_1  = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, 1)
            _rates_25 = _rates_25 if _rates_25 is not None else []
            _rates_1  = _rates_1  if _rates_1  is not None else [{"time": 0}]
            _current_time = int(_rates_1[0]["time"])
            closed_all = [r for r in _rates_25 if int(r["time"]) != _current_time]
            for i, r in enumerate(closed_all):
                if int(r["time"]) == int(entry_bar["time"]) and i > 0:
                    prev_bar = closed_all[i-1]
                    prev_high = float(prev_bar["high"])
                    prev_low  = float(prev_bar["low"])
                    break
            else:
                prev_high = float(entry_bar["high"])
                prev_low  = float(entry_bar["low"])

            entry_high = float(entry_bar["high"])
            entry_low  = float(entry_bar["low"])

                # Reverse position: special immediate close conditions
            if ticket in _reverse_tickets:
                if pos_type == "SELL" and bull and current_price > prev_high:
                # SELL reverse: green candle + close > prev high -> close immediately
                    reason_rev = f"Reverse SELL green close={current_price:.2f} > prev_high={prev_high:.2f}"
                    ok_rev, cp_rev = _close_position(pos, pos_type, "reverse entry green > prev high")
                    if ok_rev:
                        _entry_state[ticket] = "done"
                        _reverse_tickets.discard(ticket)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "reverse_close", ticket=ticket, side=pos_type, state="done", close_price=cp_rev, reason=reason_rev)
                        await tg(app, f"❌ *ปิด SELL Reverse - เขียว > prev High*\n🔴 Ticket:`{ticket}` ปิดที่`{cp_rev}`\n📊 Close:`{current_price:.2f}` > PrevHigh:`{prev_high:.2f}`")
                        print(f"❌ [{now}] {reason_rev} -> ปิดที่ {cp_rev}")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                    continue
                elif pos_type == "BUY" and not bull and current_price < prev_low:
                # BUY reverse: red candle + close < prev low -> close immediately
                    reason_rev = f"Reverse BUY red close={current_price:.2f} < prev_low={prev_low:.2f}"
                    ok_rev, cp_rev = _close_position(pos, pos_type, "reverse entry red < prev low")
                    if ok_rev:
                        _entry_state[ticket] = "done"
                        _reverse_tickets.discard(ticket)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "reverse_close", ticket=ticket, side=pos_type, state="done", close_price=cp_rev, reason=reason_rev)
                        await tg(app, f"❌ *ปิด BUY Reverse - แดง < prev Low*\n🟢 Ticket:`{ticket}` ปิดที่`{cp_rev}`\n📊 Close:`{current_price:.2f}` < PrevLow:`{prev_low:.2f}`")
                        print(f"❌ [{now}] {reason_rev} -> ปิดที่ {cp_rev}")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                    continue
                else:
                    # Reverse position: normal entry candle -> done
                    if config.ENTRY_CANDLE_MODE == "close_percentage" and current_price > pos.price_open:
                        new_sl = round(float(pos.price_open) + spread_price, 2)
                        _apply_entry_sl_tp(pos, new_sl, pos.tp)
                    _entry_state[ticket] = "done"
                    _reverse_tickets.discard(ticket)
                    save_runtime_state()
                    print(f"OK [{now}] Reverse {pos_type} {ticket} entry candle OK -> done")
                    continue

            pattern_name = position_pattern.get(ticket, "") or ""
            is_reverse_entry = pattern_name.startswith("Reverse ")
            if is_reverse_entry:
                reverse_sl = None
                reverse_note = ""
                if pos_type == "BUY" and current_price > pos.price_open:
                    reverse_sl = round(float(pos.price_open) + spread_price, 2)
                    reverse_note = "entry + spread"
                elif pos_type == "SELL" and current_price < pos.price_open:
                    reverse_sl = round(float(pos.price_open) + spread_price, 2)
                    reverse_note = "entry + spread"

                if reverse_sl is not None and _price_differs(pos.sl, reverse_sl, max(spread_price / 2.0, 0.01)):
                    ok = _apply_entry_sl_tp(pos, reverse_sl, pos.tp)
                    _entry_state[ticket] = "done"
                    save_runtime_state()
                    log_event(
                        "ENTRY_QUALITY",
                        "reverse done",
                        ticket=ticket,
                        side=pos_type,
                        state="done",
                        sl=reverse_sl,
                        tp=pos.tp,
                        reason=reverse_note,
                    )
                    if ok:
                        await tg(app, _entry_update_msg(
                            f"✅ *{pos_type} Reverse Entry จบ*",
                            sig_e, ticket, reverse_sl, reverse_note
                        ))
                    print(f"OK [{now}] Reverse {pos_type} {ticket} entry done SL={reverse_sl} ({reverse_note})")
                    continue

            if pos_type == "BUY":
                if bull and body_pct >= 0.35:
                    if config.ENTRY_CANDLE_MODE == "close_percentage" and current_price > pos.price_open:
                        new_sl = round(float(pos.price_open) + spread_price, 2)
                        ok = _apply_entry_sl_tp(pos, new_sl, pos.tp)
                        if not ok:
                            print(f"[ENTRY_CLOSE_MODE] BUY modify SL failed ticket={ticket} sl={new_sl} -> retry next cycle")
                            continue
                    _entry_state[ticket] = "done"
                    fvg_order_tickets.pop(ticket, None)
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "done", ticket=ticket, side=pos_type, state="done", reason=f"green body={body_pct_int}%")
                    print(f"[ENTRY] BUY {ticket} done green body={body_pct_int}%")

                elif bull and body_pct < 0.35:
                    if config.ENTRY_CANDLE_MODE == "close_percentage" and current_price > pos.price_open:
                        new_sl = round(float(pos.price_open) + spread_price, 2)
                        ok = _apply_entry_sl_tp(pos, new_sl, pos.tp)
                        if not ok:
                            print(f"[ENTRY_CLOSE_MODE] BUY modify SL failed ticket={ticket} sl={new_sl} -> retry next cycle")
                            continue
                    _entry_state[ticket] = "waiting_next"
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "waiting_next", ticket=ticket, side=pos_type, state="waiting_next", reason=f"green body={body_pct_int}%")
                    print(f"[ENTRY] BUY {ticket} waiting_next green body={body_pct_int}%")

                elif not bull and current_price < prev_low:
                    reason = f"entry_red close={current_price:.2f}<prev_low={prev_low:.2f} immediate"
                    ok, cp = _close_position(pos, pos_type, "entry red close < prev low")
                    if ok:
                        _entry_state[ticket] = "done"
                        fvg_order_tickets.pop(ticket, None)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "close_immediate", ticket=ticket, side=pos_type, state="done", close_price=cp, candle_close=f"{current_price:.2f}", reason=reason)
                        await tg(app, f"CLOSE BUY - Entry Red < Prev Low\n{sig_e} Ticket:`{ticket}`\nEntry Close: `{current_price:.2f}`\nPrev Low: `{prev_low:.2f}`\nExecuted Close: `{cp}`\nBody: `{body_pct_int}%`")
                        print(f"[CLOSE_IMMEDIATE] BUY ticket={ticket} reason={reason} close={cp}")
                        if config.LIMIT_SWEEP:
                            tf_name = position_tf.get(ticket, "M1")
                            lookback = TF_LOOKBACK.get(tf_name, SWING_LOOKBACK)
                            rates_sweep = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, lookback + 6)
                            if rates_sweep is not None and len(rates_sweep) >= 6:
                                reason_detail = f"แท่งจบแดง close={current_price:.2f} < prev low={prev_low:.2f}"
                                await _run_limit_sweep_followup(
                                    app, ticket, pos_type, tf_name, rates_sweep, entry_bar, prev_bar, reason_detail
                                )
                        continue
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                        await tg(app, f"⚠️ *ปิด BUY ไม่สำเร็จ (entry แดง < prev low)*\n{sig_e} Ticket:`{ticket}`")

                elif not bull and config.ENTRY_CANDLE_MODE == "close_percentage" and body_pct < 0.70:
                    tick_check = mt5.symbol_info_tick(SYMBOL)
                    ask_price = float(tick_check.ask) if tick_check else None
                    entry_plus_spread = float(pos.price_open) + spread_price
                    if ask_price is not None and ask_price > entry_plus_spread:
                        new_sl = round(entry_plus_spread, 2)
                        ok = _apply_entry_sl_tp(pos, new_sl, pos.tp)
                        if not ok:
                            print(f"[ENTRY_CLOSE_MODE] BUY modify SL failed ticket={ticket} sl={new_sl} -> retry next cycle")
                            continue
                        _entry_state[ticket] = "done"
                        fvg_order_tickets.pop(ticket, None)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "done_sl_protect", ticket=ticket, side=pos_type, state="done", sl=new_sl, reason=f"red body={body_pct_int}% ask={ask_price:.2f}>entry+spread={entry_plus_spread:.2f}")
                        await tg(app, f"🛡️ *BUY Entry แดง - SL Protect*\n{sig_e} Ticket:`{ticket}`\n🛑 SL: `{new_sl}` (Entry+Spread)\n📊 Ask: `{ask_price:.2f}` > Entry+Spread: `{entry_plus_spread:.2f}`\nBody: `{body_pct_int}%`")
                        print(f"[ENTRY] BUY {ticket} done_sl_protect red body={body_pct_int}% ask={ask_price:.2f}>entry+spread SL={new_sl}")
                        if config.LIMIT_SWEEP:
                            tf_name = position_tf.get(ticket, "M1")
                            lookback = TF_LOOKBACK.get(tf_name, SWING_LOOKBACK)
                            rates_sweep = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, lookback + 6)
                            if rates_sweep is not None and len(rates_sweep) >= 6:
                                reason_detail = f"แท่งจบแดง body={body_pct_int}% ask={ask_price:.2f} > entry+spread={entry_plus_spread:.2f}"
                                await _run_limit_sweep_followup(
                                    app, ticket, pos_type, tf_name, rates_sweep, entry_bar, prev_bar, reason_detail
                                )
                    else:
                        reason = f"entry_red body={body_pct_int}% ask<=entry+spread close_percentage"
                        ok, cp = _close_position(pos, pos_type, "entry red ask<=entry+spread")
                        if ok:
                            _entry_state[ticket] = "done"
                            fvg_order_tickets.pop(ticket, None)
                            save_runtime_state()
                            log_event("ENTRY_QUALITY", "close_immediate", ticket=ticket, side=pos_type, state="done", close_price=cp, candle_close=f"{current_price:.2f}", reason=reason)
                            await tg(app, f"❌ *CLOSE BUY - Entry แดง ask<=entry+spread*\n{sig_e} Ticket:`{ticket}`\nAsk: `{ask_price}`\nEntry+Spread: `{entry_plus_spread:.2f}`\nExecuted Close: `{cp}`\nBody: `{body_pct_int}%`")
                            print(f"[CLOSE_IMMEDIATE] BUY ticket={ticket} reason={reason} close={cp}")
                            if config.LIMIT_SWEEP:
                                tf_name = position_tf.get(ticket, "M1")
                                lookback = TF_LOOKBACK.get(tf_name, SWING_LOOKBACK)
                                rates_sweep = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, lookback + 6)
                                if rates_sweep is not None and len(rates_sweep) >= 6:
                                    reason_detail = f"แท่งจบแดง body={body_pct_int}% ask<=entry+spread ปิดทันที"
                                    await _run_limit_sweep_followup(
                                        app, ticket, pos_type, tf_name, rates_sweep, entry_bar, prev_bar, reason_detail
                                    )
                            continue
                        else:
                            _entry_state[ticket] = "closing_fail"
                            save_runtime_state()
                            await tg(app, f"⚠️ *ปิด BUY ไม่สำเร็จ (entry แดง ask<=entry+spread)*\n{sig_e} Ticket:`{ticket}`")

                elif not bull and config.ENTRY_CANDLE_MODE == "close_percentage":
                    reason = f"entry_red body={body_pct_int}% mode=close_percentage immediate"
                    ok, cp = _close_position(pos, pos_type, "entry red candle close mode")
                    if ok:
                        _entry_state[ticket] = "done"
                        fvg_order_tickets.pop(ticket, None)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "close_immediate", ticket=ticket, side=pos_type, state="done", close_price=cp, candle_close=f"{current_price:.2f}", reason=reason)
                        await tg(app, f"CLOSE BUY - Entry Red\n{sig_e} Ticket:`{ticket}`\nEntry Close: `{current_price:.2f}`\nExecuted Close: `{cp}`\nBody: `{body_pct_int}%`")
                        print(f"[CLOSE_IMMEDIATE] BUY ticket={ticket} reason={reason} close={cp}")
                        if config.LIMIT_SWEEP and current_price < prev_low:
                            tf_name = position_tf.get(ticket, "M1")
                            lookback = TF_LOOKBACK.get(tf_name, SWING_LOOKBACK)
                            rates_sweep = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, lookback + 6)
                            if rates_sweep is not None and len(rates_sweep) >= 6:
                                reason_detail = f"แท่งจบแดง close={current_price:.2f} < prev low={prev_low:.2f}"
                                await _run_limit_sweep_followup(
                                    app, ticket, pos_type, tf_name, rates_sweep, entry_bar, prev_bar, reason_detail
                                )
                        # close_percentage: close immediately only, no reverse market/limit
                        continue

                        tf_name = position_tf.get(ticket, "M1")
                        sid = position_sid.get(ticket, 1)
                        candle_range = entry_high - entry_low
                        rates_swing = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, 120)
                        swing_info = _find_prev_swing_low(rates_swing) if rates_swing is not None else None
                        rev_tp = round(swing_info["price"], 2) if swing_info else None

                        if config.ENTRY_CLOSE_REVERSE_MARKET and rev_tp:
                            mkt_sl = round(entry_high + SL_BUFFER(), 2)
                            tick_r = mt5.symbol_info_tick(SYMBOL)
                            if tick_r:
                                vol = SYMBOL_CONFIG[SYMBOL]["volume"]
                                rev_r = mt5.order_send({
                                    "action":       mt5.TRADE_ACTION_DEAL,
                                    "symbol":       SYMBOL,
                                    "volume":       vol,
                                    "type":         mt5.ORDER_TYPE_SELL,
                                    "price":        float(tick_r.bid),
                                    "sl":           mkt_sl,
                                    "tp":           rev_tp,
                                    "deviation":    20,
                                    "magic":        234001,
                                    "comment":      f"{tf_name}_S{sid}_rev_market",
                                    "type_time":    mt5.ORDER_TIME_GTC,
                                    "type_filling": _get_filling_mode(),
                                })
                                if rev_r and rev_r.retcode == mt5.TRADE_RETCODE_DONE:
                                    rev_ticket = rev_r.order
                                    position_tf[rev_ticket] = tf_name
                                    position_sid[rev_ticket] = sid
                                    position_pattern[rev_ticket] = f"Reverse SELL (entry red) [{tf_name}]"
                                    _entry_state.pop(rev_ticket, None)
                                    save_runtime_state()
                                    log_event("ORDER_CREATED", "reverse_sell_market", ticket=rev_ticket, side="SELL", tf=tf_name, sl=mkt_sl, tp=rev_tp, price=float(tick_r.bid), from_ticket=ticket)
                                    await tg(app, f"🔄 *เปิด SELL Market (Reverse)*\n🔴 Ticket:`{rev_ticket}`\n📌 Entry: `{float(tick_r.bid):.2f}`\n🛑 SL: `{mkt_sl}` (Entry High+SL_BUFFER)\n🎯 TP: `{rev_tp}` (Swing Low)\n📊 TF: `{tf_name}`\n📝 จาก: `{ticket}`")
                                    print(f"[REVERSE_MARKET] SELL ticket={rev_ticket} entry={float(tick_r.bid):.2f} SL={mkt_sl} TP={rev_tp}")
                                else:
                                    rc = rev_r.retcode if rev_r else "None"
                                    cmt = rev_r.comment if rev_r else ""
                                    log_event("ORDER_FAILED", "reverse_sell_market", ticket=ticket, side="SELL", tf=tf_name, sl=mkt_sl, tp=rev_tp, price=float(tick_r.bid), retcode=rc, comment=cmt, from_ticket=ticket)
                                    print(f"[REVERSE_MARKET_FAIL] SELL retcode={rc} comment={cmt}")
                                    await tg(app, f"⚠️ *เปิด SELL Market Reverse ไม่สำเร็จ*\nretcode=`{rc}` {cmt}")

                        if config.ENTRY_CLOSE_REVERSE_LIMIT and rev_tp and candle_range > 0:
                            from mt5_utils import open_order
                            vol = SYMBOL_CONFIG[SYMBOL]["volume"]
                            lim_entry = round(entry_high + candle_range * 0.17, 2)
                            lim_sl = round(entry_high + candle_range * 0.31, 2)
                            res = open_order("SELL", vol, lim_sl, rev_tp, entry_price=lim_entry, tf=tf_name, sid=f"{sid}_rev_limit", pattern=f"Reverse SELL Limit (entry red) [{tf_name}]")
                            if res.get("success"):
                                rev_order = res["ticket"]
                                pending_order_tf[rev_order] = {
                                    "tf": tf_name, "gap_bot": lim_entry, "gap_top": lim_entry,
                                    "detect_bar_time": int(entry_bar["time"]),
                                    "signal": "SELL", "sid": sid,
                                    "pattern": f"Reverse SELL Limit (entry red) [{tf_name}]",
                                    "reverse": True,
                                }
                                save_runtime_state()
                                log_event("ORDER_CREATED", "reverse_sell_limit", ticket=rev_order, side="SELL", tf=tf_name, sl=lim_sl, tp=rev_tp, entry=lim_entry, from_ticket=ticket)
                                await tg(app, f"🔄 *ตั้ง SELL LIMIT (Reverse)*\n🔴 Ticket:`{rev_order}`\n📌 Entry: `{lim_entry:.2f}` (High+17%)\n🛑 SL: `{lim_sl:.2f}` (High+31%)\n🎯 TP: `{rev_tp}` (Swing Low)\n📊 TF: `{tf_name}`\n📝 จาก: `{ticket}`")
                                print(f"[REVERSE_LIMIT] SELL ticket={rev_order} entry={lim_entry:.2f} SL={lim_sl:.2f} TP={rev_tp}")
                            else:
                                err = res.get("error", "unknown")
                                print(f"[REVERSE_LIMIT_FAIL] SELL error={err}")
                                await tg(app, f"⚠️ *ตั้ง SELL LIMIT Reverse ไม่สำเร็จ*\n{err}")

                        if not rev_tp:
                            print(f"[REVERSE_SKIP] SELL no swing low")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                        await tg(app, f"⚠️ *ปิด BUY ไม่สำเร็จ (entry แดง)*\n{sig_e} Ticket:`{ticket}`")

                elif not bull and current_price <= pos.price_open:
                    rates_swing = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, 120)
                    swing_info = _get_s6_prev_swing_low(rates_swing, tf=tf_name) if rates_swing is not None else None
                    swing_sl = round(swing_info["price"] - 1.0, 2) if swing_info else round(entry_low - 1.0, 2)
                    bad_tp = round(float(entry_bar["open"]) - spread_price, 2)
                    reason = f"แดง High>{prev_high:.2f}" if entry_high > prev_high else (
                        f"แดง body={body_pct_int}%>=65%" if body_pct >= 0.65 else f"แดง body={body_pct_int}%<65%")
                    ok = _apply_entry_sl_tp(pos, swing_sl, bad_tp)
                    _entry_state[ticket] = "waiting_bad"
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "waiting_bad", ticket=ticket, side=pos_type, state="waiting_bad", reason=reason, sl=swing_sl, tp=bad_tp)
                    if ok:
                        title = f"⚠️ *BUY Entry แดง -> waiting\\_bad*\n{sig_e} Ticket:`{ticket}` | {reason}"
                        msg = _entry_update_msg(title, sig_e, ticket, swing_sl, "swing low", bad_tp, "entry open")
                        await tg(app, msg)
                    print(f"[{now}] BUY {ticket} {reason} -> waiting_bad SL={swing_sl} TP={bad_tp}")

                elif not bull:
                    new_sl = round(pos.price_open + 50.0, 2)
                    ok = _apply_entry_sl_tp(pos, new_sl, pos.tp)
                    _entry_state[ticket] = "done"
                    fvg_order_tickets.pop(ticket, None)
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "done", ticket=ticket, side=pos_type, state="done", reason="red candle but current above entry", sl=new_sl, tp=pos.tp)
                    if ok:
                        await tg(app, _entry_update_msg(
                            "✅ *BUY Entry แดง แต่ราคายังเหนือ entry*",
                            sig_e, ticket, new_sl, "entry + 50"
                        ))
                    print(f"[ENTRY] BUY {ticket} red entry but current>{pos.price_open:.2f} -> SL={new_sl}")

            else:  # SELL
                if not bull and body_pct >= 0.35:
                    if config.ENTRY_CANDLE_MODE == "close_percentage" and current_price < pos.price_open:
                        new_sl = round(float(pos.price_open) - spread_price, 2)
                        ok = _apply_entry_sl_tp(pos, new_sl, pos.tp)
                        if not ok:
                            print(f"[ENTRY_CLOSE_MODE] SELL modify SL failed ticket={ticket} sl={new_sl} -> retry next cycle")
                            continue
                    _entry_state[ticket] = "done"
                    fvg_order_tickets.pop(ticket, None)
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "done", ticket=ticket, side=pos_type, state="done", reason=f"red body={body_pct_int}%")
                    print(f"[ENTRY] SELL {ticket} done red body={body_pct_int}%")

                elif not bull and body_pct < 0.35:
                    if config.ENTRY_CANDLE_MODE == "close_percentage" and current_price < pos.price_open:
                        new_sl = round(float(pos.price_open) - spread_price, 2)
                        ok = _apply_entry_sl_tp(pos, new_sl, pos.tp)
                        if not ok:
                            print(f"[ENTRY_CLOSE_MODE] SELL modify SL failed ticket={ticket} sl={new_sl} -> retry next cycle")
                            continue
                    _entry_state[ticket] = "waiting_next"
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "waiting_next", ticket=ticket, side=pos_type, state="waiting_next", reason=f"red body={body_pct_int}%")
                    print(f"[ENTRY] SELL {ticket} waiting_next red body={body_pct_int}%")

                elif bull and current_price > prev_high:
                    reason = f"entry_green close={current_price:.2f}>prev_high={prev_high:.2f} immediate"
                    ok, cp = _close_position(pos, pos_type, "entry green close > prev high")
                    if ok:
                        _entry_state[ticket] = "done"
                        fvg_order_tickets.pop(ticket, None)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "close_immediate", ticket=ticket, side=pos_type, state="done", close_price=cp, candle_close=f"{current_price:.2f}", reason=reason)
                        await tg(app, f"CLOSE SELL - Entry Green > Prev High\n{sig_e} Ticket:`{ticket}`\nEntry Close: `{current_price:.2f}`\nPrev High: `{prev_high:.2f}`\nExecuted Close: `{cp}`\nBody: `{body_pct_int}%`")
                        print(f"[CLOSE_IMMEDIATE] SELL ticket={ticket} reason={reason} close={cp}")
                        if config.LIMIT_SWEEP:
                            tf_name = position_tf.get(ticket, "M1")
                            lookback = TF_LOOKBACK.get(tf_name, SWING_LOOKBACK)
                            rates_sweep = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, lookback + 6)
                            if rates_sweep is not None and len(rates_sweep) >= 6:
                                reason_detail = f"แท่งจบเขียว close={current_price:.2f} > prev high={prev_high:.2f}"
                                await _run_limit_sweep_followup(
                                    app, ticket, pos_type, tf_name, rates_sweep, entry_bar, prev_bar, reason_detail
                                )
                        continue
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                        await tg(app, f"⚠️ *ปิด SELL ไม่สำเร็จ (entry เขียว > prev high)*\n{sig_e} Ticket:`{ticket}`")

                elif bull and config.ENTRY_CANDLE_MODE == "close_percentage" and body_pct < 0.70:
                    tick_check = mt5.symbol_info_tick(SYMBOL)
                    bid_price = float(tick_check.bid) if tick_check else None
                    entry_minus_spread = float(pos.price_open) - spread_price
                    if bid_price is not None and bid_price < entry_minus_spread:
                        new_sl = round(entry_minus_spread, 2)
                        ok = _apply_entry_sl_tp(pos, new_sl, pos.tp)
                        if not ok:
                            print(f"[ENTRY_CLOSE_MODE] SELL modify SL failed ticket={ticket} sl={new_sl} -> retry next cycle")
                            continue
                        _entry_state[ticket] = "done"
                        fvg_order_tickets.pop(ticket, None)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "done_sl_protect", ticket=ticket, side=pos_type, state="done", sl=new_sl, reason=f"green body={body_pct_int}% bid={bid_price:.2f}<entry-spread={entry_minus_spread:.2f}")
                        await tg(app, f"🛡️ *SELL Entry เขียว - SL Protect*\n{sig_e} Ticket:`{ticket}`\n🛑 SL: `{new_sl}` (Entry-Spread)\n📊 Bid: `{bid_price:.2f}` < Entry-Spread: `{entry_minus_spread:.2f}`\nBody: `{body_pct_int}%`")
                        print(f"[ENTRY] SELL {ticket} done_sl_protect green body={body_pct_int}% bid={bid_price:.2f}<entry-spread SL={new_sl}")
                        if config.LIMIT_SWEEP:
                            tf_name = position_tf.get(ticket, "M1")
                            lookback = TF_LOOKBACK.get(tf_name, SWING_LOOKBACK)
                            rates_sweep = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, lookback + 6)
                            if rates_sweep is not None and len(rates_sweep) >= 6:
                                reason_detail = f"แท่งจบเขียว body={body_pct_int}% bid={bid_price:.2f} < entry-spread={entry_minus_spread:.2f}"
                                await _run_limit_sweep_followup(
                                    app, ticket, pos_type, tf_name, rates_sweep, entry_bar, prev_bar, reason_detail
                                )
                    else:
                        reason = f"entry_green body={body_pct_int}% bid>=entry-spread close_percentage"
                        ok, cp = _close_position(pos, pos_type, "entry green bid>=entry-spread")
                        if ok:
                            _entry_state[ticket] = "done"
                            fvg_order_tickets.pop(ticket, None)
                            save_runtime_state()
                            log_event("ENTRY_QUALITY", "close_immediate", ticket=ticket, side=pos_type, state="done", close_price=cp, candle_close=f"{current_price:.2f}", reason=reason)
                            await tg(app, f"❌ *CLOSE SELL - Entry เขียว bid>=entry-spread*\n{sig_e} Ticket:`{ticket}`\nBid: `{bid_price}`\nEntry-Spread: `{entry_minus_spread:.2f}`\nExecuted Close: `{cp}`\nBody: `{body_pct_int}%`")
                            print(f"[CLOSE_IMMEDIATE] SELL ticket={ticket} reason={reason} close={cp}")
                            if config.LIMIT_SWEEP:
                                tf_name = position_tf.get(ticket, "M1")
                                lookback = TF_LOOKBACK.get(tf_name, SWING_LOOKBACK)
                                rates_sweep = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, lookback + 6)
                                if rates_sweep is not None and len(rates_sweep) >= 6:
                                    reason_detail = f"แท่งจบเขียว body={body_pct_int}% bid>=entry-spread ปิดทันที"
                                    await _run_limit_sweep_followup(
                                        app, ticket, pos_type, tf_name, rates_sweep, entry_bar, prev_bar, reason_detail
                                    )
                            continue
                        else:
                            _entry_state[ticket] = "closing_fail"
                            save_runtime_state()
                            await tg(app, f"⚠️ *ปิด SELL ไม่สำเร็จ (entry เขียว bid>=entry-spread)*\n{sig_e} Ticket:`{ticket}`")

                elif bull and config.ENTRY_CANDLE_MODE == "close_percentage":
                    reason = f"entry_green body={body_pct_int}% mode=close_percentage immediate"
                    ok, cp = _close_position(pos, pos_type, "entry green candle close mode")
                    if ok:
                        _entry_state[ticket] = "done"
                        fvg_order_tickets.pop(ticket, None)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "close_immediate", ticket=ticket, side=pos_type, state="done", close_price=cp, candle_close=f"{current_price:.2f}", reason=reason)
                        await tg(app, f"CLOSE SELL - Entry Green\n{sig_e} Ticket:`{ticket}`\nEntry Close: `{current_price:.2f}`\nExecuted Close: `{cp}`\nBody: `{body_pct_int}%`")
                        print(f"[CLOSE_IMMEDIATE] SELL ticket={ticket} reason={reason} close={cp}")
                        if config.LIMIT_SWEEP and current_price > prev_high:
                            tf_name = position_tf.get(ticket, "M1")
                            lookback = TF_LOOKBACK.get(tf_name, SWING_LOOKBACK)
                            rates_sweep = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, lookback + 6)
                            if rates_sweep is not None and len(rates_sweep) >= 6:
                                reason_detail = f"แท่งจบเขียว close={current_price:.2f} > prev high={prev_high:.2f}"
                                await _run_limit_sweep_followup(
                                    app, ticket, pos_type, tf_name, rates_sweep, entry_bar, prev_bar, reason_detail
                                )
                        # close_percentage: close immediately only, no reverse market/limit
                        continue

                        tf_name = position_tf.get(ticket, "M1")
                        sid = position_sid.get(ticket, 1)
                        candle_range = entry_high - entry_low
                        rates_swing = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, 120)
                        swing_info = _find_prev_swing_high(rates_swing) if rates_swing is not None else None
                        rev_tp = round(swing_info["price"], 2) if swing_info else None

                        if config.ENTRY_CLOSE_REVERSE_MARKET and rev_tp:
                            mkt_sl = round(entry_low - SL_BUFFER(), 2)
                            tick_r = mt5.symbol_info_tick(SYMBOL)
                            if tick_r:
                                vol = SYMBOL_CONFIG[SYMBOL]["volume"]
                                rev_r = mt5.order_send({
                                    "action":       mt5.TRADE_ACTION_DEAL,
                                    "symbol":       SYMBOL,
                                    "volume":       vol,
                                    "type":         mt5.ORDER_TYPE_BUY,
                                    "price":        float(tick_r.ask),
                                    "sl":           mkt_sl,
                                    "tp":           rev_tp,
                                    "deviation":    20,
                                    "magic":        234001,
                                    "comment":      f"{tf_name}_S{sid}_rev_market",
                                    "type_time":    mt5.ORDER_TIME_GTC,
                                    "type_filling": _get_filling_mode(),
                                })
                                if rev_r and rev_r.retcode == mt5.TRADE_RETCODE_DONE:
                                    rev_ticket = rev_r.order
                                    position_tf[rev_ticket] = tf_name
                                    position_sid[rev_ticket] = sid
                                    position_pattern[rev_ticket] = f"Reverse BUY (entry green) [{tf_name}]"
                                    _entry_state.pop(rev_ticket, None)
                                    save_runtime_state()
                                    log_event("ORDER_CREATED", "reverse_buy_market", ticket=rev_ticket, side="BUY", tf=tf_name, sl=mkt_sl, tp=rev_tp, price=float(tick_r.ask), from_ticket=ticket)
                                    await tg(app, f"🔄 *เปิด BUY Market (Reverse)*\n🟢 Ticket:`{rev_ticket}`\n📌 Entry: `{float(tick_r.ask):.2f}`\n🛑 SL: `{mkt_sl}` (Entry Low-SL_BUFFER)\n🎯 TP: `{rev_tp}` (Swing High)\n📊 TF: `{tf_name}`\n📝 จาก: `{ticket}`")
                                    print(f"[REVERSE_MARKET] BUY ticket={rev_ticket} entry={float(tick_r.ask):.2f} SL={mkt_sl} TP={rev_tp}")
                                else:
                                    rc = rev_r.retcode if rev_r else "None"
                                    cmt = rev_r.comment if rev_r else ""
                                    log_event("ORDER_FAILED", "reverse_buy_market", ticket=ticket, side="BUY", tf=tf_name, sl=mkt_sl, tp=rev_tp, price=float(tick_r.ask), retcode=rc, comment=cmt, from_ticket=ticket)
                                    print(f"[REVERSE_MARKET_FAIL] BUY retcode={rc} comment={cmt}")
                                    await tg(app, f"⚠️ *เปิด BUY Market Reverse ไม่สำเร็จ*\nretcode=`{rc}` {cmt}")

                        if config.ENTRY_CLOSE_REVERSE_LIMIT and rev_tp and candle_range > 0:
                            from mt5_utils import open_order
                            vol = SYMBOL_CONFIG[SYMBOL]["volume"]
                            lim_entry = round(entry_low - candle_range * 0.17, 2)
                            lim_sl = round(entry_low - candle_range * 0.31, 2)
                            res = open_order("BUY", vol, lim_sl, rev_tp, entry_price=lim_entry, tf=tf_name, sid=f"{sid}_rev_limit", pattern=f"Reverse BUY Limit (entry green) [{tf_name}]")
                            if res.get("success"):
                                rev_order = res["ticket"]
                                pending_order_tf[rev_order] = {
                                    "tf": tf_name, "gap_bot": lim_entry, "gap_top": lim_entry,
                                    "detect_bar_time": int(entry_bar["time"]),
                                    "signal": "BUY", "sid": sid,
                                    "pattern": f"Reverse BUY Limit (entry green) [{tf_name}]",
                                    "reverse": True,
                                }
                                save_runtime_state()
                                log_event("ORDER_CREATED", "reverse_buy_limit", ticket=rev_order, side="BUY", tf=tf_name, sl=lim_sl, tp=rev_tp, entry=lim_entry, from_ticket=ticket)
                                await tg(app, f"🔄 *ตั้ง BUY LIMIT (Reverse)*\n🟢 Ticket:`{rev_order}`\n📌 Entry: `{lim_entry:.2f}` (Low-17%)\n🛑 SL: `{lim_sl:.2f}` (Low-31%)\n🎯 TP: `{rev_tp}` (Swing High)\n📊 TF: `{tf_name}`\n📝 จาก: `{ticket}`")
                                print(f"[REVERSE_LIMIT] BUY ticket={rev_order} entry={lim_entry:.2f} SL={lim_sl:.2f} TP={rev_tp}")
                            else:
                                err = res.get("error", "unknown")
                                print(f"[REVERSE_LIMIT_FAIL] BUY error={err}")
                                await tg(app, f"⚠️ *ตั้ง BUY LIMIT Reverse ไม่สำเร็จ*\n{err}")

                        if not rev_tp:
                            print(f"[REVERSE_SKIP] BUY no swing high")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                        await tg(app, f"⚠️ *ปิด SELL ไม่สำเร็จ (entry เขียว)*\n{sig_e} Ticket:`{ticket}`")

                elif bull and current_price >= pos.price_open:
                    rates_swing = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, 120)
                    swing_info = _get_s6_prev_swing_high(rates_swing, tf=tf_name) if rates_swing is not None else None
                    swing_sl = round(swing_info["price"] + 1.0, 2) if swing_info else round(entry_high + 1.0, 2)
                    bad_tp = round(float(entry_bar["open"]) + spread_price, 2)
                    reason = f"เขียว Low<{prev_low:.2f}" if entry_low < prev_low else (
                        f"เขียว body={body_pct_int}%>=65%" if body_pct >= 0.65 else f"เขียว body={body_pct_int}%<65%")
                    ok = _apply_entry_sl_tp(pos, swing_sl, bad_tp)
                    _entry_state[ticket] = "waiting_bad"
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "waiting_bad", ticket=ticket, side=pos_type, state="waiting_bad", reason=reason, sl=swing_sl, tp=bad_tp)
                    if ok:
                        title = f"⚠️ *SELL Entry เขียว -> waiting\\_bad*\n{sig_e} Ticket:`{ticket}` | {reason}"
                        msg = _entry_update_msg(title, sig_e, ticket, swing_sl, "swing high", bad_tp, "entry open")
                        await tg(app, msg)
                    print(f"⏳ [{now}] SELL {ticket} {reason} -> waiting_bad SL={swing_sl} TP={bad_tp}")

                elif bull:
                    new_sl = round(pos.price_open - 50.0, 2)
                    ok = _apply_entry_sl_tp(pos, new_sl, pos.tp)
                    _entry_state[ticket] = "done"
                    fvg_order_tickets.pop(ticket, None)
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "done", ticket=ticket, side=pos_type, state="done", reason="green candle but current below entry", sl=new_sl, tp=pos.tp)
                    if ok:
                        await tg(app, _entry_update_msg(
                            "✅ *SELL Entry เขียว แต่ราคายังต่ำกว่า entry*",
                            sig_e, ticket, new_sl, "entry - 50"
                        ))
                    print(f"OK [{now}] SELL {ticket} green entry but current<{pos.price_open:.2f} -> SL={new_sl}")

        elif state == "closing_fail":
            # Retry close silently
            ok, cp = _close_position(pos, pos_type, "retry_close")
            if ok:
                _entry_state[ticket] = "done"
                save_runtime_state()
                await tg(app, f"✅ *retry ปิด {pos_type} สำเร็จ*\n{sig_e} Ticket:`{ticket}` ปิดที่`{cp}`")
                print(f"OK [{now}] retry close {pos_type} {ticket} สำเร็จ @ {cp}")
            else:
                print(f"FAIL [{now}] retry close {pos_type} {ticket} ยังไม่สำเร็จ")
            continue

        elif state == "waiting_next":
            # Candle after entry
            if next_bar is None:
                continue

            bull_next, _, _ = bar_info(next_bar)
            next_c = float(next_bar["close"])
            entry_h = float(entry_bar["high"])
            entry_l = float(entry_bar["low"])

            if pos_type == "BUY":
                # Close when: red candle + Close < Low[entry]
                if not bull_next and next_c < entry_l:
                    ok, cp = _close_position(pos, pos_type, "waiting_next: red close < entry low")
                    if ok:
                        _entry_state[ticket] = "done"
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "waiting_next close", ticket=ticket, side=pos_type, state="done", close_price=cp, reason="red close < entry low")
                        await tg(app, f"❌ *ปิด BUY - แดง Close<Low[entry]*\n{sig_e} Ticket:`{ticket}` ปิดที่`{cp}`")
                        print(f"❌ [{now}] ปิด BUY {ticket} แดง Close:{next_c:.2f}<Low[entry]:{entry_l:.2f}")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                        await tg(app, f"⚠️ *ปิด BUY ไม่สำเร็จ (waiting_next)*\n{sig_e} Ticket:`{ticket}`")
                else:
                # Pass -> set SL=next.low-1.0, TP=next.open (same as waiting_bad)
                    next_l = float(next_bar["low"])
                    next_o = float(next_bar["open"])
                    new_sl = round(next_l - 1.0, 2)
                    sl_note = "next low"
                    if new_sl < pos.price_open:
                        new_sl = round(pos.price_open + spread_price, 2)
                        sl_note = "entry+spread (next low < entry)"
                    new_tp = round(next_o - spread_price, 2)
                    tp_note = "next open - spread"
                    if new_tp < pos.price_open:
                        new_tp  = round(pos.price_open, 2)
                        tp_note = "entry (next open < entry)"
                    ok = _apply_entry_sl_tp(pos, new_sl, new_tp)
                    if not ok:
                        print(f"WARN [{now}] BUY {ticket} waiting_next modify SL failed sl={new_sl} -> retry next cycle")
                        continue
                    _entry_state[ticket] = "done"
                    fvg_order_tickets.pop(ticket, None)
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "waiting_next done", ticket=ticket, side=pos_type, state="done", sl=new_sl, tp=new_tp, reason=tp_note)
                    await tg(app, _entry_update_msg(
                        "✅ *BUY waiting\\_next -> done*",
                        sig_e, ticket, new_sl, sl_note, new_tp, tp_note
                    ))
                    print(f"OK [{now}] BUY {ticket} waiting_next->done SL={new_sl} TP={new_tp} ({sl_note}, {tp_note})")

            else:  # SELL
                # Close when: green candle + Close > High[entry]
                if bull_next and next_c > entry_h:
                    ok, cp = _close_position(pos, pos_type, "waiting_next: green close > entry high")
                    if ok:
                        _entry_state[ticket] = "done"
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "waiting_next close", ticket=ticket, side=pos_type, state="done", close_price=cp, reason="green close > entry high")
                        await tg(app, f"❌ *ปิด SELL - เขียว Close>High[entry]*\n{sig_e} Ticket:`{ticket}` ปิดที่`{cp}`")
                        print(f"❌ [{now}] ปิด SELL {ticket} เขียว Close:{next_c:.2f}>High[entry]:{entry_h:.2f}")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                        await tg(app, f"⚠️ *ปิด SELL ไม่สำเร็จ (waiting_next)*\n{sig_e} Ticket:`{ticket}`")
                else:
                    # Pass -> set SL=next.high+1.0, TP=next.open (same as waiting_bad)
                    next_h2 = float(next_bar["high"])
                    next_o  = float(next_bar["open"])
                    new_sl  = round(next_h2 + 1.0, 2)
                    sl_note = "next high"
                    if new_sl > pos.price_open:
                        new_sl = round(pos.price_open - spread_price, 2)
                        sl_note = "entry-spread (next high > entry)"
                    new_tp  = round(next_o + spread_price, 2)
                    tp_note = "next open + spread"
                    if new_tp > pos.price_open:
                        new_tp  = round(pos.price_open, 2)
                        tp_note = "entry (next open > entry)"
                    ok = _apply_entry_sl_tp(pos, new_sl, new_tp)
                    if not ok:
                        print(f"WARN [{now}] SELL {ticket} waiting_next modify SL failed sl={new_sl} -> retry next cycle")
                        continue
                    _entry_state[ticket] = "done"
                    fvg_order_tickets.pop(ticket, None)
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "waiting_next done", ticket=ticket, side=pos_type, state="done", sl=new_sl, tp=new_tp, reason=tp_note)
                    await tg(app, _entry_update_msg(
                        "✅ *SELL waiting\\_next -> done*",
                        sig_e, ticket, new_sl, sl_note, new_tp, tp_note
                    ))
                    print(f"OK [{now}] SELL {ticket} waiting_next->done SL={new_sl} TP={new_tp} ({sl_note}, {tp_note})")

        elif state == "waiting_bad":
            # Candle after entry (red entry for BUY / green entry for SELL)
            if next_bar is None:
                continue

            next_c = float(next_bar["close"])
            next_h = float(next_bar["high"])
            next_l = float(next_bar["low"])

            if pos_type == "BUY":
                orig_tp = pos.tp  # original order TP
                if next_c >= pos.price_open:
                    print(f"[{now}] WAITING_BAD_CLOSE BUY ticket={ticket} next_close={next_c:.2f} entry={pos.price_open:.2f} next_high={next_h:.2f} next_low={next_l:.2f}")
                    ok, cp = _close_position(pos, pos_type, "waiting_bad: close >= entry")
                    if ok:
                        _entry_state[ticket] = "done"
                        fvg_order_tickets.pop(ticket, None)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "waiting_bad close", ticket=ticket, side=pos_type, state="done", close_price=cp, reason="close >= entry")
                        await tg(app, f"❌ *ปิด BUY -> waiting\\_bad close>=entry*\n{sig_e} Ticket:`{ticket}` ปิดที่`{cp}`")
                        print(f"❌ [{now}] ปิด BUY {ticket} waiting_bad close:{next_c:.2f}>=entry:{pos.price_open:.2f}")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                        await tg(app, f"⚠️ *ปิด BUY ไม่สำเร็จ (waiting_bad)*\n{sig_e} Ticket:`{ticket}`")
                    continue
                    # close >= entry -> SL = entry + 0.5, TP unchanged
                    new_sl = round(pos.price_open + 0.5, 2)
                    new_tp = orig_tp
                    sl_note = "entry+0.5"
                else:
                    # close < entry -> SL = next.low - 1.0, TP unchanged
                    new_sl  = round(next_l - 1.0, 2)
                    new_tp  = orig_tp
                    sl_note = "next low"
                    if new_sl < pos.price_open:
                        new_sl = round(pos.price_open + spread_price, 2)
                        sl_note = "entry+spread (next low < entry)"
                    if new_tp < pos.price_open:
                        new_tp = round(pos.price_open, 2)
                ok = _apply_entry_sl_tp(pos, new_sl, new_tp)
                if not ok:
                    print(f"WARN [{now}] BUY {ticket} waiting_bad modify SL failed sl={new_sl} -> retry next cycle")
                    continue
                _entry_state[ticket] = "done"
                fvg_order_tickets.pop(ticket, None)
                save_runtime_state()
                log_event("ENTRY_QUALITY", "waiting_bad done", ticket=ticket, side=pos_type, state="done", sl=new_sl, tp=new_tp, reason=sl_note)
                await tg(app, _entry_update_msg(
                    "✅ *BUY waiting\\_bad -> done*",
                    sig_e, ticket, new_sl, sl_note, new_tp
                ))
                print(f"OK [{now}] BUY {ticket} waiting_bad->done SL={new_sl} TP={new_tp} ({sl_note})")

            else:  # SELL
                orig_tp = pos.tp  # original order TP
                if next_c <= pos.price_open:
                    print(f"[{now}] WAITING_BAD_CLOSE SELL ticket={ticket} next_close={next_c:.2f} entry={pos.price_open:.2f} next_high={next_h:.2f} next_low={next_l:.2f}")
                    ok, cp = _close_position(pos, pos_type, "waiting_bad: close <= entry")
                    if ok:
                        _entry_state[ticket] = "done"
                        fvg_order_tickets.pop(ticket, None)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "waiting_bad close", ticket=ticket, side=pos_type, state="done", close_price=cp, reason="close <= entry")
                        await tg(app, f"❌ *ปิด SELL -> waiting\\_bad close<=entry*\n{sig_e} Ticket:`{ticket}` ปิดที่`{cp}`")
                        print(f"❌ [{now}] ปิด SELL {ticket} waiting_bad close:{next_c:.2f}<=entry:{pos.price_open:.2f}")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                        await tg(app, f"⚠️ *ปิด SELL ไม่สำเร็จ (waiting_bad)*\n{sig_e} Ticket:`{ticket}`")
                    continue
                    # close <= entry -> SL = entry - 0.5, TP unchanged
                    new_sl = round(pos.price_open - 0.5, 2)
                    new_tp = orig_tp
                    sl_note = "entry-0.5"
                else:
                    # close > entry -> SL = next.high + 1.0, TP unchanged
                    new_sl  = round(next_h + 1.0, 2)
                    new_tp  = orig_tp
                    sl_note = "next high"
                    if new_sl > pos.price_open:
                        new_sl = round(pos.price_open - spread_price, 2)
                        sl_note = "entry-spread (next high > entry)"
                    if new_tp > pos.price_open:
                        new_tp = round(pos.price_open, 2)
                ok = _apply_entry_sl_tp(pos, new_sl, new_tp)
                if not ok:
                    print(f"WARN [{now}] SELL {ticket} waiting_bad modify SL failed sl={new_sl} -> retry next cycle")
                    continue
                _entry_state[ticket] = "done"
                fvg_order_tickets.pop(ticket, None)
                save_runtime_state()
                log_event("ENTRY_QUALITY", "waiting_bad done", ticket=ticket, side=pos_type, state="done", sl=new_sl, tp=new_tp, reason=sl_note)
                await tg(app, _entry_update_msg(
                    "✅ *SELL waiting\\_bad -> done*",
                    sig_e, ticket, new_sl, sl_note, new_tp
                ))
                print(f"OK [{now}] SELL {ticket} waiting_bad->done SL={new_sl} TP={new_tp} ({sl_note})")


# -------------------------------------------------------------
async def check_engulf_trail_sl(app):
    """
    Trail SL by TF group.
    phase 1: check engulf on lower TFs in the group (group[1:]) -> move SL -> enter phase 2
    phase 2: check engulf on the order TF itself (group[0]) -> move SL -> done

    combined mode:
    - merge phases by TF group
    - check every TF in the group each cycle
    - keep moving SL when a better engulf result appears

    Groups from TRAIL_GROUPS:
      D1  -> [D1, H12, H4]
      H12 -> [H12, H4, H1]
      ...
      M1  -> [M1]
    """
    global _last_trail_tg_key
    if not getattr(config, "TRAIL_SL_ENABLED", True):
        return
    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        _bar_count.clear()
        _trail_state.clear()
        _trend_filter_last_dir.clear()
        return

    # Cleanup tickets that are already closed
    open_tickets = {p.ticket for p in positions}
    for t in list(_trail_state.keys()):
        if t not in open_tickets:
            _trail_state.pop(t, None)
    for key in list(_trend_filter_last_dir.keys()):
        try:
            t = int(str(key).split("|", 1)[0])
        except (TypeError, ValueError):
            _trend_filter_last_dir.pop(key, None)
            continue
        if t not in open_tickets:
            _trend_filter_last_dir.pop(key, None)
    for t in list(_fill_notified.keys()):
        if t not in open_tickets:
            _fill_notified.pop(t, None)
    for t in list(_entry_bar_notified.keys()):
        if t not in open_tickets:
            _entry_bar_notified.pop(t, None)
    for t in list(_fill_rsi_checked):
        if t not in open_tickets:
            _fill_rsi_checked.discard(t)

    now = now_bkk().strftime("%H:%M:%S")

    # Trail SL Focus Opposite (frozen_side marker)
    # Same side as marker -> freeze every position (do not trail)
    # Opposite side -> allow trailing only after the gate passes
    focus_skip_tickets: set[int] = set()
    if getattr(config, "TRAIL_SL_FOCUS_NEW_ENABLED", False):
        pending_focus = mt5.orders_get(symbol=SYMBOL) or []
        frozen_side_ts = _focus_update_frozen_side("trail_sl", positions, pending_focus)
        if frozen_side_ts is not None:
            for p in positions:
                p_side = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
                if p_side == frozen_side_ts:
                    focus_skip_tickets.add(p.ticket)
                elif not _focus_gate_passed(
                    "trail_sl", frozen_side_ts, positions, position_tf.get(p.ticket)
                ):
                    focus_skip_tickets.add(p.ticket)

    for pos in positions:
        ticket   = pos.ticket
        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        sid      = position_sid.get(ticket)
        if sid in (10, 12, 13, 15, 16, 17, 18, 19, 20, 20.5, 20.6, 20.7):
            continue  # standalone strategies (S15 = VP absorption, exit ด้วย fixed TP/SL; S18 = TJR; S19 = ICT SB)
        # Resolve order timeframe
        fvg_info = fvg_order_tickets.get(ticket)
        order_tf = position_tf.get(ticket, "M1")
        if fvg_info:
            order_tf = fvg_info.get("tf", "M1")

        if not config.TRAIL_SL_IMMEDIATE and _entry_state.get(ticket) != "done":
            continue

        # Trail SL only when price is beyond entry:
        # above entry for BUY, below entry for SELL
        tick = mt5.symbol_info_tick(SYMBOL)
        if tick:
            if pos_type == "BUY" and tick.bid <= pos.price_open:
                continue
            if pos_type == "SELL" and tick.ask >= pos.price_open:
                continue

        trend_override, trend_override_reason = _trend_filter_trail_override(ticket, pos_type, order_tf)
        # Reversal override เฉพาะเมื่อ SL lock profit แล้ว
        # BUY: SL > entry | SELL: SL < entry (SL = 0 ยังไม่ตั้ง → ข้าม)
        _entry_price = float(pos.price_open)
        _cur_sl      = float(pos.sl)
        _sl_in_profit = (
            (pos_type == "BUY"  and _cur_sl > _entry_price) or
            (pos_type == "SELL" and _cur_sl > 0 and _cur_sl < _entry_price)
        )
        if _sl_in_profit:
            reversal_override, reversal_sl, reversal_override_reason = _reversal_trail_override(
                pos_type, order_tf, _cur_sl, int(pos.time)
            )
        else:
            reversal_override, reversal_sl, reversal_override_reason = False, 0.0, ""
        if ticket in focus_skip_tickets and not trend_override and not reversal_override:
            continue

        mode = getattr(config, "TRAIL_SL_ENGULF_MODE", "separate")

        # init trail state
        if ticket not in _trail_state:
            group = TRAIL_GROUPS.get(order_tf, [order_tf])
            # combined = keep checking every TF in the group continuously
            if mode == "combined":
                phase = 0
            else:
                # phase 1 when smaller TFs exist, otherwise start at phase 2
                phase = 1 if len(group) > 1 else 2
            _trail_state[ticket] = {"phase": phase, "order_tf": order_tf}

        state    = _trail_state[ticket]
        phase    = state["phase"]
        group    = TRAIL_GROUPS.get(order_tf, [order_tf])

        # Phase 2 already done -> stop trailing (separate mode only)
        if mode != "combined" and phase > 2:
            continue

        # Choose TFs to inspect in this phase
        if mode == "combined":
            check_tfs = group
        elif phase == 1:
            # Check smaller TFs first, e.g. H4 order -> H1, M30
            check_tfs = group[1:] if len(group) > 1 else group
        else:
            # phase 2: check only the order TF itself
            check_tfs = [group[0]]

        new_sl       = 0.0
        engulf_found = False
        engulf_tf    = None
        label        = ""

        for tf_name in check_tfs:
            tf_val   = TF_OPTIONS.get(tf_name, mt5.TIMEFRAME_M1)
            lookback = min(TF_LOOKBACK.get(tf_name, SWING_LOOKBACK), 50)
            rates    = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, lookback)
            if rates is None or len(rates) < 3:
                continue

            # Find the entry bar
            # rates["time"] is MT5 server time (UTC+MT5_SERVER_TZ) stored as-if-UTC,
            # so it is numerically (MT5_SERVER_TZ * 3600) seconds ahead of pos.time (real UTC).
            _mt5_tz_trail = getattr(config, "MT5_SERVER_TZ", 1) * 3600
            _pos_time_adj = pos.time + _mt5_tz_trail
            entry_bar_time = 0
            for r in rates:
                t = int(r["time"])
                if t <= _pos_time_adj and t > entry_bar_time:
                    entry_bar_time = t
            if entry_bar_time == 0:
                continue

            bars_after = [r for r in rates if int(r["time"]) >= entry_bar_time]
            if len(bars_after) < 2:
                continue

            # Count closed bars since entry
            cur_bar_time = int(bars_after[-1]["time"])
            key_last = f"{ticket}_{tf_name}_last"
            if cur_bar_time != _bar_count.get(key_last, 0):
                _bar_count[key_last] = cur_bar_time
                _bar_count[f"{ticket}_{tf_name}"] = _bar_count.get(f"{ticket}_{tf_name}", 0) + 1

            # Find the best engulf candidate in this TF
            current_sl = pos.sl
            found_in_tf = False
            for i in range(1, len(bars_after)):
                cur  = bars_after[i]; prev = bars_after[i-1]
                cur_c = float(cur["close"]); cur_o = float(cur["open"])
                cur_h = float(cur["high"]);  cur_l = float(cur["low"])
                prev_h = float(prev["high"]); prev_l = float(prev["low"])
                bull   = cur_c > cur_o

                if pos_type == "BUY" and bull and cur_c > prev_h:
                    candidate = round(cur_l - 1.0, 2)
                    if candidate > current_sl:
                        current_sl = candidate; found_in_tf = True

                elif pos_type == "SELL" and not bull and cur_c < prev_l:
                    candidate = round(cur_h + 1.0, 2)
                    if current_sl == 0 or candidate < current_sl:
                        current_sl = candidate; found_in_tf = True

            if found_in_tf and current_sl != pos.sl:
                # Keep the TF that gives the best SL
                if pos_type == "BUY" and (new_sl == 0 or current_sl > new_sl):
                    new_sl = current_sl; engulf_found = True
                    engulf_tf = tf_name; label = f"Trail SL [{tf_name}] Engulf"
                elif pos_type == "SELL" and (new_sl == 0 or current_sl < new_sl):
                    new_sl = current_sl; engulf_found = True
                    engulf_tf = tf_name; label = f"Trail SL [{tf_name}] Engulf"

        # Protective SL if no engulf appears within 3 bars
        if not engulf_found:
            if reversal_override and reversal_sl > 0:
                new_sl = reversal_sl
                label = f"Trail SL [{order_tf}] Reversal"
            main_tf  = group[0]
            key_cnt  = f"{ticket}_{main_tf}"
            bar_cnt  = _bar_count.get(key_cnt, 0)
            if new_sl == 0 and bar_cnt >= 3 and not state.get("had_engulf"):
                entry_price = pos.price_open
                if pos_type == "BUY":
                    safe = round(entry_price + 0.5, 2)
                    if safe > pos.sl:
                        new_sl = safe; label = f"SL Protect [{main_tf}] +50pt"
                else:
                    safe = round(entry_price - 0.5, 2)
                    if pos.sl == 0 or safe < pos.sl:
                        new_sl = safe; label = f"SL Protect [{main_tf}] -50pt"

        # Check whether the latest closed candle is already beyond entry
        main_tf_val = TF_OPTIONS.get(group[0], mt5.TIMEFRAME_M1)
        latest_rates = mt5.copy_rates_from_pos(SYMBOL, main_tf_val, 1, 1)
        entry_price  = pos.price_open
        price_past_entry = False
        if latest_rates is not None and len(latest_rates) > 0:
            latest_close = float(latest_rates[0]["close"])
            if pos_type == "BUY" and latest_close > entry_price:
                price_past_entry = True
            elif pos_type == "SELL" and latest_close < entry_price:
                price_past_entry = True

        if new_sl > 0:
            old_sl = float(pos.sl)
            if _modify_sl(pos, new_sl):
                sig_e = "🟢" if pos_type == "BUY" else "🔴"

                # Mark that this ticket has had at least one engulf trail
                if engulf_found:
                    _trail_state[ticket]["had_engulf"] = True

                # Advance phase only after price closes beyond entry
                if engulf_found and mode == "combined":
                    phase_note = f"combined mode (found on {engulf_tf}, keep trailing SL)"
                elif engulf_found:
                    if phase == 1:
                        if price_past_entry:
                            _trail_state[ticket]["phase"] = 2
                            save_runtime_state()
                            phase_note = f"phase 1->2 (found on {engulf_tf}, price passed entry)"
                        else:
                            phase_note = f"phase 1 pending (found on {engulf_tf}, waiting for price to pass entry)"
                    else:  # phase 2
                        if price_past_entry:
                            _trail_state[ticket]["phase"] = 3  # done
                            save_runtime_state()
                            phase_note = f"phase 2->done (found on {engulf_tf}, price passed entry)"
                        else:
                            phase_note = f"phase 2 pending (found on {engulf_tf}, waiting for price to pass entry)"
                else:
                    phase_note = "reversal override" if reversal_override else "SL Protect"
                if trend_override:
                    phase_note = f"{phase_note} | override {trend_override_reason}"
                if reversal_override:
                    phase_note = f"{phase_note} | {reversal_override_reason}" if phase_note else reversal_override_reason

                log_event(
                    "SL_CHANGED",
                    "trail_engulf" if engulf_found else "trail_safe",
                    ticket=ticket,
                    side=pos_type,
                    tf=order_tf,
                    old_sl=old_sl,
                    new_sl=float(new_sl),
                    reason=phase_note,
                    source=(engulf_tf if engulf_found else group[0]),
                    trend_override=trend_override,
                )
                trail_tg_key = f"{ticket}|{label}|{old_sl:.2f}|{float(new_sl):.2f}|{phase_note}"
                if trail_tg_key != _last_trail_tg_key:
                    await tg(app, (f"📐 *{label} - {pos_type}*\n"
                              f"{sig_e} Ticket:`{ticket}` [{order_tf}]\n"
                              f"🛑 SL: `{old_sl}` -> `{new_sl}`\n"
                              f"📋 {phase_note}"))
                    _last_trail_tg_key = trail_tg_key
                print(f"📐 [{now}] {label} {pos_type} {ticket}: {old_sl}->{new_sl} | {phase_note}")


# -------------------------------------------------------------
async def check_opposite_order_tp(app):
    """
    Opposite-side TP handling within the same timeframe:
    1) BUY position in profit + SELL limit -> set BUY TP to SELL limit entry
    2) SELL position in profit + BUY limit -> set SELL TP to BUY limit entry
    3) If both BUY and SELL positions exist on the same TF, handle them by the configured mode
    """
    if not getattr(config, "OPPOSITE_ORDER_ENABLED", True):
        return
    positions = mt5.positions_get(symbol=SYMBOL)
    pending   = mt5.orders_get(symbol=SYMBOL)
    if not positions:
        return

    global _last_sl_protect_tg_key
    open_tickets = {p.ticket for p in positions}
    for t in list(_sl_protect_applied):
        if t not in open_tickets:
            _sl_protect_applied.discard(t)

    now      = now_bkk().strftime("%H:%M:%S")
    # S15 (VP) ถือ BUY (VAL) + SELL (VAH) พร้อมกันได้ (range play) → ห้ามให้ Opposite Order ปิดฝั่งตรงข้ามทิ้ง
    opposite_skip_sids = set(getattr(config, "OPPOSITE_ORDER_SKIP_SIDS", (10, 12, 13, 15, 16, 17, 18, 19)))
    buy_pos  = [p for p in positions if p.type == mt5.ORDER_TYPE_BUY and position_sid.get(p.ticket) not in opposite_skip_sids]
    sell_pos = [p for p in positions if p.type == mt5.ORDER_TYPE_SELL and position_sid.get(p.ticket) not in opposite_skip_sids]

    def _get_order_tf(ticket):
        info = pending_order_tf.get(ticket)
        if isinstance(info, dict):
            return info.get("tf")
        return info

    def _get_order_sid(ticket):
        info = pending_order_tf.get(ticket)
        if isinstance(info, dict):
            return info.get("sid")
        return None

    opp_mode = config.OPPOSITE_ORDER_MODE  # "tp_close" | "sl_protect"

    if pending and opp_mode == "tp_close":
        buy_lim  = [o for o in pending if o.type == mt5.ORDER_TYPE_BUY_LIMIT and _get_order_sid(o.ticket) not in opposite_skip_sids]
        sell_lim = [o for o in pending if o.type == mt5.ORDER_TYPE_SELL_LIMIT and _get_order_sid(o.ticket) not in opposite_skip_sids]

        # BUY position in profit + SELL limit on same TF -> BUY TP = SELL limit entry
        for pos in buy_pos:
            if pos.profit <= 0:
                continue
            pos_tf = position_tf.get(pos.ticket)
            if not pos_tf:
                continue
            for ord_ in sell_lim:
                ord_tf = _get_order_tf(ord_.ticket)
                if ord_tf != pos_tf:
                    continue
                se = ord_.price_open
                if _price_differs(pos.tp, se, 0.5):
                    old_sl, old_tp = float(pos.sl), float(pos.tp)
                    r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "symbol": SYMBOL,
                                        "position": pos.ticket, "sl": pos.sl, "tp": se})
                    ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
                    _audit_sltp_event("opposite_tp:buy_link", pos, old_sl, old_tp, float(pos.sl), float(se), ok, r)
                    if ok:
                        log_event(
                            "TP_CHANGED",
                            "opposite_tp_buy_link",
                            ticket=pos.ticket,
                            side="BUY",
                            tf=pos_tf,
                            old_tp=old_tp,
                            new_tp=float(se),
                            old_sl=old_sl,
                            new_sl=float(pos.sl),
                        )
                        await _notify_sltp_audit(app, "opposite_tp:buy_link", pos, old_sl, old_tp, float(pos.sl), float(se), True)
                        if _trade_debug_enabled():
                            print(f"🔄 [{now}] BUY {pos.ticket} [{pos_tf}] TP->{se}")

        # SELL position in profit + BUY limit on same TF -> SELL TP = BUY limit entry
        for pos in sell_pos:
            if pos.profit <= 0:
                continue
            pos_tf = position_tf.get(pos.ticket)
            if not pos_tf:
                continue
            for ord_ in buy_lim:
                ord_tf = _get_order_tf(ord_.ticket)
                if ord_tf != pos_tf:
                    continue
                be = ord_.price_open
                if _price_differs(pos.tp, be, 0.5):
                    old_sl, old_tp = float(pos.sl), float(pos.tp)
                    r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "symbol": SYMBOL,
                                        "position": pos.ticket, "sl": pos.sl, "tp": be})
                    ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
                    _audit_sltp_event("opposite_tp:sell_link", pos, old_sl, old_tp, float(pos.sl), float(be), ok, r)
                    if ok:
                        log_event(
                            "TP_CHANGED",
                            "opposite_tp_sell_link",
                            ticket=pos.ticket,
                            side="SELL",
                            tf=pos_tf,
                            old_tp=old_tp,
                            new_tp=float(be),
                            old_sl=old_sl,
                            new_sl=float(pos.sl),
                        )
                        await _notify_sltp_audit(app, "opposite_tp:sell_link", pos, old_sl, old_tp, float(pos.sl), float(be), True)
                        if _trade_debug_enabled():
                            print(f"🔄 [{now}] SELL {pos.ticket} [{pos_tf}] TP->{be}")

    # Both BUY and SELL positions exist on the same TF
    if buy_pos and sell_pos:
        spread = _get_spread_price()
        for bp in buy_pos:
            bp_tf = position_tf.get(bp.ticket)
            if not bp_tf:
                continue
            for sp in sell_pos:
                sp_tf = position_tf.get(sp.ticket)
                if sp_tf != bp_tf:
                    continue

                if opp_mode == "tp_close":
                    # tp_close: close the older position
                    if bp.time > sp.time:
                        ok, cp = _close_position(sp, "SELL", f"Close SELL - BUY filled [{bp_tf}]")
                        if ok:
                            await tg(app, (f"❒ *ปิด SELL - BUY Limit Fill [{bp_tf}]*\n"
                                      f"🔴 Ticket:`{sp.ticket}` ปิดที่`{cp}`"))
                            print(f"❒ [{now}] ปิด SELL {sp.ticket} BUY fill [{bp_tf}]")
                    elif sp.time > bp.time:
                        ok, cp = _close_position(bp, "BUY", f"Close BUY - SELL filled [{bp_tf}]")
                        if ok:
                            await tg(app, (f"❒ *ปิด BUY - SELL Limit Fill [{bp_tf}]*\n"
                                      f"🟢 Ticket:`{bp.ticket}` ปิดที่`{cp}`"))
                            print(f"❒ [{now}] ปิด BUY {bp.ticket} SELL fill [{bp_tf}]")

                else:
                    # sl_protect: set SL to entry +/- spread without closing
                    if bp.time > sp.time:
                        # BUY filled later -> protect SELL with entry - spread
                        new_sl = round(sp.price_open - spread, 2)
                        if sp.ticket in _sl_protect_applied:
                            continue
                        if _price_differs(sp.sl, new_sl, 0.3):
                            old_sl, old_tp = float(sp.sl), float(sp.tp)
                            r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "symbol": SYMBOL,
                                                "position": sp.ticket, "sl": new_sl, "tp": sp.tp})
                            ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
                            _audit_sltp_event("opposite_sl:sell_protect", sp, old_sl, old_tp, float(new_sl), float(sp.tp), ok, r)
                            if ok:
                                _sl_protect_applied.add(sp.ticket)
                                log_event(
                                    "SL_CHANGED",
                                    "sl_protect_sell_fill",
                                    ticket=sp.ticket,
                                    side="SELL",
                                    tf=bp_tf,
                                    old_sl=old_sl,
                                    new_sl=float(new_sl),
                                    old_tp=old_tp,
                                    new_tp=float(sp.tp),
                                )
                                protect_tg_key = f"SELL|{sp.ticket}|{bp_tf}|{old_sl:.2f}|{new_sl:.2f}"
                                if protect_tg_key != _last_sl_protect_tg_key:
                                    await tg(app, (f"🛡️ *SELL SL Protect - BUY Fill [{bp_tf}]*\n"
                                                  f"🔴 Ticket:`{sp.ticket}`\n"
                                                  f"🛑 SL: `{old_sl:.2f}` -> `{new_sl:.2f}` (entry-spread)"))
                                    _last_sl_protect_tg_key = protect_tg_key
                                print(f"🛡️ [{now}] SELL {sp.ticket} SL->{new_sl} (entry={sp.price_open:.2f}-spread={spread:.2f})")
                    elif sp.time > bp.time:
                        # SELL filled later -> protect BUY with entry + spread
                        new_sl = round(bp.price_open + spread, 2)
                        if bp.ticket in _sl_protect_applied:
                            continue
                        if _price_differs(bp.sl, new_sl, 0.3):
                            old_sl, old_tp = float(bp.sl), float(bp.tp)
                            r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "symbol": SYMBOL,
                                                "position": bp.ticket, "sl": new_sl, "tp": bp.tp})
                            ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
                            _audit_sltp_event("opposite_sl:buy_protect", bp, old_sl, old_tp, float(new_sl), float(bp.tp), ok, r)
                            if ok:
                                _sl_protect_applied.add(bp.ticket)
                                log_event(
                                    "SL_CHANGED",
                                    "sl_protect_buy_fill",
                                    ticket=bp.ticket,
                                    side="BUY",
                                    tf=bp_tf,
                                    old_sl=old_sl,
                                    new_sl=float(new_sl),
                                    old_tp=old_tp,
                                    new_tp=float(bp.tp),
                                )
                                protect_tg_key = f"BUY|{bp.ticket}|{bp_tf}|{old_sl:.2f}|{new_sl:.2f}"
                                if protect_tg_key != _last_sl_protect_tg_key:
                                    await tg(app, (f"🛡️ *BUY SL Protect - SELL Fill [{bp_tf}]*\n"
                                                  f"🟢 Ticket:`{bp.ticket}`\n"
                                                  f"🛑 SL: `{old_sl:.2f}` -> `{new_sl:.2f}` (entry+spread)"))
                                    _last_sl_protect_tg_key = protect_tg_key
                                print(f"🛡️ [{now}] BUY {bp.ticket} SL->{new_sl} (entry={bp.price_open:.2f}+spread={spread:.2f})")


async def check_breakeven_tp(app):
    """
    Breakeven TP logic for every strategy.
    After the entry candle, if price moves against the position and the latest
    closed candle shows a rejection/engulf pattern, set TP back to entry.

    BUY:
      price below entry and latest candle closes red:
        - engulf: Close < Low[prev]
        - rejection: Low[cur] < Low[prev] and Close stays inside prev body

    SELL:
      price above entry and latest candle closes green:
        - engulf: Close > High[prev]
        - rejection: High[cur] > High[prev] and Close stays inside prev body
    """
    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        return

    now = now_bkk().strftime("%H:%M:%S")

    for pos in positions:
        ticket   = pos.ticket
        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        entry    = pos.price_open

        # Only after entry candle flow is done
        if _entry_state.get(ticket) != "done":
            continue

        # TP already equals entry -> nothing to do
        if abs(pos.tp - entry) < 0.5:
            continue

        # Timeframe of this order
        fvg_info = fvg_order_tickets.get(ticket)
        pos_tf_name = position_tf.get(ticket, "M1")
        if fvg_info:
            tf_val = TF_OPTIONS.get(fvg_info.get("tf","M1"), mt5.TIMEFRAME_M1)
        else:
            tf_val = TF_OPTIONS.get(pos_tf_name, mt5.TIMEFRAME_M1)

        rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, 10)
        if rates is None or len(rates) < 3:
            continue

        # Latest closed candle and previous candle
        cur  = rates[-1]
        prev = rates[-2]

        cur_o  = float(cur["open"]);  cur_c  = float(cur["close"])
        cur_h  = float(cur["high"]);  cur_l  = float(cur["low"])
        prev_o = float(prev["open"]); prev_c = float(prev["close"])
        prev_h = float(prev["high"]); prev_l = float(prev["low"])
        bull_cur = cur_c > cur_o

        trigger = False
        reason  = ""

        if pos_type == "BUY":
            # Price moved below entry
            tick = mt5.symbol_info_tick(SYMBOL)
            if not tick or tick.bid >= entry:
                continue
            if not bull_cur:  # latest candle closes red
                # engulf: Close < Low[prev]
                if cur_c < prev_l:
                    trigger = True
                    reason  = f"แดงกลืนกิน Close:{cur_c:.2f} < Low[prev]:{prev_l:.2f}"
                # rejection: Low[cur] < Low[prev] and Close remains in prev range
                elif cur_l < prev_l and prev_l <= cur_c <= prev_h:
                    trigger = True
                    reason  = f"แดงปฏิเสธ Low:{cur_l:.2f} < Low[prev]:{prev_l:.2f}"

        else:  # SELL
            tick = mt5.symbol_info_tick(SYMBOL)
            if not tick or tick.ask <= entry:
                continue
            if bull_cur:  # latest candle closes green
                # engulf: Close > High[prev]
                if cur_c > prev_h:
                    trigger = True
                    reason  = f"เขียวกลืนกิน Close:{cur_c:.2f} > High[prev]:{prev_h:.2f}"
                # rejection: High[cur] > High[prev] and Close remains in prev range
                elif cur_h > prev_h and prev_l <= cur_c <= prev_h:
                    trigger = True
                    reason  = f"เขียวปฏิเสธ High:{cur_h:.2f} > High[prev]:{prev_h:.2f}"

        if trigger:
            print(f"[{now}] 🎯 DEBUG breakeven: {pos_type} {ticket} entry={entry} tp_now={pos.tp} cur={cur_c:.2f} prev_h={prev_h:.2f} prev_l={prev_l:.2f} ask/bid={(mt5.symbol_info_tick(SYMBOL).ask if pos_type=='SELL' else mt5.symbol_info_tick(SYMBOL).bid):.2f}")
            old_sl = float(pos.sl)
            old_tp = float(pos.tp)
            r = mt5.order_send({
                "action":   mt5.TRADE_ACTION_SLTP,
                "symbol":   SYMBOL,
                "position": ticket,
                "sl":       pos.sl,
                "tp":       entry,
            })
            ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
            _audit_sltp_event("check_breakeven_tp", pos, old_sl, old_tp, float(pos.sl), float(entry), ok, r)
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                await _notify_sltp_audit(app, "check_breakeven_tp", pos, old_sl, old_tp, float(pos.sl), float(entry), True)
                sig_e = "🟢" if pos_type == "BUY" else "🔴"
                await tg(app, (
                        f"🎯 *ตั้ง TP = Breakeven*\n"
                        f"{sig_e} Ticket:`{ticket}` [{pos_tf_name}]\n"
                        f"TP: `{pos.tp}` -> `{entry}` (entry)\n"
                        f"เหตุผล: {reason}"
                    ))
                if _trade_debug_enabled():
                    print(f"🎯 [{now}] Breakeven {pos_type} {ticket}: TP->{entry} ({reason})")


async def _s6_process_ticket(app, pos, positions, state_dict, mode_tag, now,
                             _find_prev_swing_high, _find_prev_swing_low, strategy_1):
    """
    Shared core logic for strategy 6.
    Used by both the original S6 flow and the independent S6i flow.
    mode_tag is either "S6" or "S6i" for logging.
    """
    ticket   = pos.ticket
    pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
    sig_e    = "🟢" if pos_type == "BUY" else "🔴"
    entry    = pos.price_open

    tf_name  = position_tf.get(ticket, "M1")
    tf_val   = TF_OPTIONS.get(tf_name, mt5.TIMEFRAME_M1)
    lookback = min(TF_LOOKBACK.get(tf_name, SWING_LOOKBACK) + 6, 60)
    rates    = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, lookback)
    if rates is None or len(rates) < 5:
        return

    # Check strategy 1 on every scan, both in wait and count phases
    r1 = strategy_1(rates)
    s1_signal = r1.get("signal", "WAIT")
    s1_entry  = r1.get("entry", 0)
    s1_is_opposite = (pos_type == "BUY" and s1_signal == "SELL") or \
                     (pos_type == "SELL" and s1_signal == "BUY")

    if s1_is_opposite:
        st = state_dict.get(ticket)
        in_wait_phase = st is None or st.get("phase") == "wait"

        if in_wait_phase:
            if s1_entry > 0:
                new_tp = round(s1_entry, 2)
                if _tp_valid_for_side(pos_type, entry, new_tp, 0.01):
                    old_sl = float(pos.sl)
                    old_tp = float(pos.tp)
                    r = mt5.order_send({
                        "action":   mt5.TRADE_ACTION_SLTP,
                        "symbol":   SYMBOL,
                        "position": ticket,
                        "sl":       pos.sl,
                        "tp":       new_tp,
                    })
                    ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
                    _audit_sltp_event(f"{mode_tag}:s1_entry", pos, old_sl, old_tp, float(pos.sl), float(new_tp), ok, r)
                    if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                        await _notify_sltp_audit(app, f"{mode_tag}:s1_entry", pos, old_sl, old_tp, float(pos.sl), float(new_tp), True)
                        if ticket not in state_dict:
                            state_dict[ticket] = {}
                        state_dict[ticket]["tp_set_by_s1"] = new_tp
                        await tg(app, (f"🎯 *{mode_tag} ตั้ง TP = ท่า1 Entry*\n"
                                  f"{sig_e} Ticket:`{ticket}` [{tf_name}]\n"
                                  f"ท่า1 {s1_signal} entry={s1_entry:.2f}\n"
                                  f"TP: `{pos.tp}` -> `{new_tp:.2f}`"))
                        if _trade_debug_enabled():
                            print(f"🎯 [{now}] {mode_tag} {ticket} TP->{new_tp:.2f} (ท่า1 {s1_signal})")
                else:
                    print(f"WARN [{now}] {mode_tag} skip invalid TP from S1 entry ticket={ticket} type={pos_type} entry={entry:.2f} new_tp={new_tp:.2f}")
        else:
            sell_positions = [p for p in positions
                              if p.type == mt5.ORDER_TYPE_SELL and p.ticket != ticket]
            if sell_positions or st.get("tp_set_by_s1"):
                ok, cp = _close_position(pos, pos_type, f"{mode_tag}: ท่า1 opposite trigger")
                if ok:
                    state_dict.pop(ticket, None)
                    await tg(app, (f"❒ *ปิด {pos_type} {mode_tag} - ท่า1 {s1_signal} trigger*\n"
                              f"{sig_e} Ticket:`{ticket}` [{tf_name}] ปิดที่`{cp:.2f}`"))
                    print(f"❒ [{now}] {mode_tag} ปิด {pos_type} {ticket} ท่า1 trigger")
                return

    # Init state
    if ticket not in state_dict:
        if pos_type == "BUY":
            sh_info = _get_s6_prev_swing_high(rates, tf=tf_name)
            swing_ref = sh_info["price"] if sh_info else None
        else:
            sl_info = _get_s6_prev_swing_low(rates, tf=tf_name)
            swing_ref = sl_info["price"] if sl_info else None

        if not swing_ref:
            return
        state_dict[ticket] = {
            "swing_h": swing_ref,
            "phase":   "wait",
            "count":   0,
            "last_bar_time": 0,
            "trail_count": 0,
        }
        print(f"🆕 [{now}] {mode_tag} {pos_type} {ticket} init swing={swing_ref:.2f}")

    st = state_dict[ticket]
    swing_h = st["swing_h"]

    # Latest closed candle
    cur_bar = rates[-1]
    cur_time = int(cur_bar["time"])
    cur_h  = float(cur_bar["high"])
    cur_l  = float(cur_bar["low"])
    cur_c  = float(cur_bar["close"])
    cur_o  = float(cur_bar["open"])
    bull   = cur_c > cur_o

    # Phase "wait": wait for price to touch swing_h
    if st["phase"] == "wait":
        touched = (pos_type == "BUY" and cur_h >= swing_h) or \
                  (pos_type == "SELL" and cur_l <= swing_h)
        if touched:
            st["phase"] = "count"
            st["count"] = 0
            st["last_bar_time"] = 0
            print(f"🎯 [{now}] {mode_tag} {ticket} touched swing={swing_h:.2f} start counting")
        return

    # Phase "count": count 1-5 candles
    if cur_time == st["last_bar_time"]:
        return  # Same candle, do not count twice

    st["last_bar_time"] = cur_time
    st["count"] += 1

    if pos_type == "BUY":
        broke_out = bull and cur_c > swing_h
    else:
        broke_out = (not bull) and cur_c < swing_h

    if broke_out:
        # Trail SL
        if pos_type == "BUY":
            new_sl = round(cur_l - 1.0, 2)
            if new_sl < entry and new_sl > pos.sl:
                if _modify_sl(pos, new_sl):
                    st["trail_count"] += 1
                    await tg(app, (f"📐 *{mode_tag} Trail SL รอบ{st['trail_count']} - BUY*\n"
                              f"{sig_e} Ticket:`{ticket}` [{tf_name}]\n"
                              f"แท่งปิดเหนือ Swing:{swing_h:.2f}\n"
                              f"O:`{cur_o:.2f}` H:`{cur_h:.2f}` L:`{cur_l:.2f}` C:`{cur_c:.2f}`\n"
                              f"🛑 SL: `{pos.sl}` -> `{new_sl}`"))
                    print(f"📐 [{now}] {mode_tag} Trail BUY {ticket}: {pos.sl}->{new_sl}")
            else:
                print(f"WARN [{now}] {mode_tag} Trail BUY {ticket}: new_sl={new_sl} invalid (entry={entry} pos.sl={pos.sl})")
        else:
            new_sl = round(cur_h + 1.0, 2)
            if new_sl > entry and (pos.sl == 0 or new_sl < pos.sl):
                if _modify_sl(pos, new_sl):
                    st["trail_count"] += 1
                    await tg(app, (f"📐 *{mode_tag} Trail SL รอบ{st['trail_count']} - SELL*\n"
                              f"{sig_e} Ticket:`{ticket}` [{tf_name}]\n"
                              f"แท่งปิดใต้ Swing:{swing_h:.2f}\n"
                              f"O:`{cur_o:.2f}` H:`{cur_h:.2f}` L:`{cur_l:.2f}` C:`{cur_c:.2f}`\n"
                              f"🛑 SL: `{pos.sl}` -> `{new_sl}`"))
                    print(f"📐 [{now}] {mode_tag} Trail SELL {ticket}: {pos.sl}->{new_sl}")
            else:
                print(f"WARN [{now}] {mode_tag} Trail SELL {ticket}: new_sl={new_sl} invalid (entry={entry} pos.sl={pos.sl})")

        # Find a new swing from the breakout candle -> reset state
        if pos_type == "BUY":
            sh_info = _get_s6_prev_swing_high(rates, tf=tf_name)
            new_swing = sh_info["price"] if sh_info and sh_info["price"] > swing_h else None
        else:
            sl_info = _get_s6_prev_swing_low(rates, tf=tf_name)
            new_swing = sl_info["price"] if sl_info and sl_info["price"] < swing_h else None

        if new_swing:
            st["swing_h"] = new_swing
            st["phase"]   = "wait"
            st["count"]   = 0
            print(f"🔄 [{now}] {mode_tag} {ticket} new swing={new_swing:.2f} wait for touch")
        else:
            state_dict.pop(ticket, None)
            print(f"OK [{now}] {mode_tag} {ticket} no new swing, done")

    elif st["count"] >= 5:
        # Reached 5 candles without breakout -> set TP to entry
        old_sl = float(pos.sl)
        old_tp = float(pos.tp)
        r = mt5.order_send({
            "action":   mt5.TRADE_ACTION_SLTP,
            "symbol":   SYMBOL,
            "position": ticket,
            "sl":       pos.sl,
            "tp":       entry,
        })
        ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
        _audit_sltp_event(f"{mode_tag}:count5_breakeven", pos, old_sl, old_tp, float(pos.sl), float(entry), ok, r)
        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
            await _notify_sltp_audit(app, f"{mode_tag}:count5_breakeven", pos, old_sl, old_tp, float(pos.sl), float(entry), True)
            state_dict.pop(ticket, None)
            await tg(app, (f"🎯 *{mode_tag} TP = Breakeven*\n"
                      f"{sig_e} Ticket:`{ticket}` ครบ 5 แท่งไม่ผ่าน swing\n"
                      f"TP -> `{entry}`"))
            print(f"🎯 [{now}] {mode_tag} {ticket} TP=entry={entry}")


# S6i helpers: check S1/S3 patterns without using zone filters

def _has_s1_sell_pattern(rates):
    """S1 SELL pattern without zone filter: green[2]->red[1]->red[0] close<low[1]."""
    if len(rates) < 4:
        return False
    o0, h0, l0, c0 = [float(rates[-1][k]) for k in ('open','high','low','close')]
    o1, h1, l1, c1 = [float(rates[-2][k]) for k in ('open','high','low','close')]
    o2, h2, l2, c2 = [float(rates[-3][k]) for k in ('open','high','low','close')]
    bull0, bull1, bull2 = c0 > o0, c1 > o1, c2 > o2
    return bull2 and not bull1 and not bull0 and c0 < l1


def _has_s1_buy_pattern(rates):
    """S1 BUY pattern without zone filter: red[2]->green[1]->green[0] close>high[1]."""
    if len(rates) < 4:
        return False
    o0, h0, l0, c0 = [float(rates[-1][k]) for k in ('open','high','low','close')]
    o1, h1, l1, c1 = [float(rates[-2][k]) for k in ('open','high','low','close')]
    o2, h2, l2, c2 = [float(rates[-3][k]) for k in ('open','high','low','close')]
    bull0, bull1, bull2 = c0 > o0, c1 > o1, c2 > o2
    return not bull2 and bull1 and bull0 and c0 > h1


def _has_s3_sell_pattern(rates):
    """S3 SP SELL pattern without zone filter: red[2] body>=35% -> green/doji[1] -> red[0] close<low[1]."""
    if len(rates) < 4:
        return False
    o0, h0, l0, c0 = [float(rates[-1][k]) for k in ('open','high','low','close')]
    o1, h1, l1, c1 = [float(rates[-2][k]) for k in ('open','high','low','close')]
    o2, h2, l2, c2 = [float(rates[-3][k]) for k in ('open','high','low','close')]
    r2 = h2 - l2; b2 = abs(c2 - o2)
    bull0, bull1, bull2 = c0 > o0, c1 > o1, c2 > o2
    bp2 = (b2 / r2 * 100) if r2 > 0 else 0
    r1 = h1 - l1; doji1 = (abs(c1 - o1) / r1 * 100 if r1 > 0 else 0) < 10
    return not bull2 and bp2 >= 35 and (bull1 or doji1) and not bull0 and c0 < l1


def _has_s3_buy_pattern(rates):
    """S3 SP BUY pattern without zone filter: green[2] body>=35% -> red/doji[1] -> green[0] close>high[1]."""
    if len(rates) < 4:
        return False
    o0, h0, l0, c0 = [float(rates[-1][k]) for k in ('open','high','low','close')]
    o1, h1, l1, c1 = [float(rates[-2][k]) for k in ('open','high','low','close')]
    o2, h2, l2, c2 = [float(rates[-3][k]) for k in ('open','high','low','close')]
    r2 = h2 - l2; b2 = abs(c2 - o2)
    bull0, bull1, bull2 = c0 > o0, c1 > o1, c2 > o2
    bp2 = (b2 / r2 * 100) if r2 > 0 else 0
    r1 = h1 - l1; doji1 = (abs(c1 - o1) / r1 * 100 if r1 > 0 else 0) < 10
    return bull2 and bp2 >= 35 and (not bull1 or doji1) and bull0 and c0 > h1


def _has_opposite_order_near(side, price, tolerance=2.0):
    """Return True when a pending order on the given side is near the target price."""
    orders = mt5.orders_get(symbol=SYMBOL)
    if not orders:
        return False
    otype = mt5.ORDER_TYPE_SELL_LIMIT if side == "SELL" else mt5.ORDER_TYPE_BUY_LIMIT
    return any(o.type == otype and abs(o.price_open - price) <= tolerance for o in orders)


# S6i: independent strategy 6 state machine

async def _s6i_process_ticket(app, pos, now,
                              _find_prev_swing_high, _find_prev_swing_low):
    """
    S6i - 2 High 2 Low Independent.
    Phase: watch -> count -> wait_swing2 -> order_placed

    SELL: find swing HIGH (resistance) -> check pattern -> set TP/order
    BUY:  find swing LOW (support)     -> mirrored logic
    """
    ticket   = pos.ticket
    pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
    sig_e    = "🟢" if pos_type == "BUY" else "🔴"
    is_buy   = pos_type == "BUY"

    tf_name  = position_tf.get(ticket, "M1")
    tf_val   = TF_OPTIONS.get(tf_name, mt5.TIMEFRAME_M1)
    lookback = min(TF_LOOKBACK.get(tf_name, SWING_LOOKBACK) + 6, 60)
    rates    = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, lookback)
    if rates is None or len(rates) < 5:
        return

    # Side-dependent references — ใช้ HHLL ก่อน fallback pivot/simple
    find_swing    = (lambda r: _get_s6_prev_swing_low(r, tf=tf_name))  if is_buy else (lambda r: _get_s6_prev_swing_high(r, tf=tf_name))
    find_swing_tp = (lambda r: _get_s6_prev_swing_high(r, tf=tf_name)) if is_buy else (lambda r: _get_s6_prev_swing_low(r, tf=tf_name))
    has_s1        = _has_s1_buy_pattern   if is_buy else _has_s1_sell_pattern
    has_s3        = _has_s3_buy_pattern   if is_buy else _has_s3_sell_pattern
    order_side    = "BUY" if is_buy else "SELL"
    opp_lim_type  = mt5.ORDER_TYPE_SELL_LIMIT if is_buy else mt5.ORDER_TYPE_BUY_LIMIT
    our_lim_type  = mt5.ORDER_TYPE_BUY_LIMIT  if is_buy else mt5.ORDER_TYPE_SELL_LIMIT

    # Init: find swing, check S1/S3 pattern, set TP
    if ticket not in _s6i_state:
        sw_info   = find_swing(rates)
        swing_ref = sw_info["price"] if sw_info else None
        if not swing_ref:
            return

        s1_found = (has_s1(rates) or has_s3(rates) or
                    _has_opposite_order_near(order_side, swing_ref))

        tp_source = None
        if not s1_found:
            # TP = entry of opposite limit (strategy 2/3) or swing TP
            pending = mt5.orders_get(symbol=SYMBOL)
            opp_entry = None
            if pending:
                opp_limits = [o for o in pending if o.type == opp_lim_type]
                if opp_limits:
                    opp_entry  = opp_limits[0].price_open
                    tp_source  = opp_limits[0].ticket

            if opp_entry is None:
                sw_tp = find_swing_tp(rates)
                opp_entry = sw_tp["price"] if sw_tp else None

            if opp_entry and abs(pos.tp - opp_entry) > 0.5 and _tp_valid_for_side(pos_type, pos.price_open, round(opp_entry, 2), 0.01):
                old_sl = float(pos.sl)
                old_tp = float(pos.tp)
                r = mt5.order_send({
                    "action":   mt5.TRADE_ACTION_SLTP,
                    "symbol":   SYMBOL,
                    "position": ticket,
                    "sl":       pos.sl,
                    "tp":       round(opp_entry, 2),
                })
                ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
                _audit_sltp_event("S6i:init_tp", pos, old_sl, old_tp, float(pos.sl), round(opp_entry, 2), ok, r)
                if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                    log_event(
                        "TP_CHANGED",
                        "s6i_init_tp",
                        ticket=ticket,
                        side=pos_type,
                        tf=tf_name,
                        old_tp=old_tp,
                        new_tp=round(opp_entry, 2),
                        old_sl=old_sl,
                        new_sl=float(pos.sl),
                    )
                    await _notify_sltp_audit(app, "S6i:init_tp", pos, old_sl, old_tp, float(pos.sl), round(opp_entry, 2), True)
                    await tg(app, (f"🎯 *S6i ตั้ง TP - {pos_type}*\n"
                              f"{sig_e} Ticket:`{ticket}` [{tf_name}]\n"
                              f"TP: `{pos.tp}` -> `{opp_entry:.2f}`"))
                    if _trade_debug_enabled():
                        print(f"🎯 [{now}] S6i {ticket} TP->{opp_entry:.2f}")
            elif opp_entry and not _tp_valid_for_side(pos_type, pos.price_open, round(opp_entry, 2), 0.01):
                print(f"WARN [{now}] S6i skip invalid TP ticket={ticket} type={pos_type} entry={pos.price_open:.2f} new_tp={opp_entry:.2f}")

        _s6i_state[ticket] = {
            "swing_h1":   swing_ref,
            "phase":      "watch",
            "s1_found":   s1_found,
            "count":      0,
            "last_bar_time": 0,
            "swing_h2":   None,
            "order_ticket": None,
            "tp_source":  tp_source,
        }
        print(f"🆕 [{now}] S6i {pos_type} {ticket} init swing={swing_ref:.2f} s1={s1_found}")

    st     = _s6i_state[ticket]
    swing1 = st["swing_h1"]

    # Monitor: close the position when the opposite limit fills
    if st.get("tp_source"):
        pending = mt5.orders_get(symbol=SYMBOL)
        still_exists = pending and any(o.ticket == st["tp_source"] for o in pending)
        if not still_exists:
            ok, cp = _close_position(pos, pos_type, "S6i: opposite limit filled")
            if ok:
                _s6i_state.pop(ticket, None)
                await tg(app, (f"❒ *ปิด {pos_type} S6i - ฝั่งตรงข้าม fill*\n"
                          f"{sig_e} Ticket:`{ticket}` [{tf_name}] ปิดที่`{cp:.2f}`"))
                print(f"❒ [{now}] S6i ปิด {pos_type} {ticket} opposite fill")
            return

    # Current bar
    cur_bar  = rates[-1]
    cur_time = int(cur_bar["time"])
    cur_c    = float(cur_bar["close"])
    cur_o    = float(cur_bar["open"])
    cur_h    = float(cur_bar["high"])
    cur_l    = float(cur_bar["low"])
    bull     = cur_c > cur_o

    # Phase: watch -> wait to see whether the candle closes beyond swing
    if st["phase"] == "watch":
        if cur_time == st["last_bar_time"]:
            return
        st["last_bar_time"] = cur_time

        # SELL: green close > swing_h1 -> breakout -> find a new swing
        # BUY:  red close < swing_l1 -> breakout -> find a new swing
        broke_out     = (bull and cur_c > swing1) if not is_buy else (not bull and cur_c < swing1)
        # SELL: green close <= swing_h1 -> enter count
        # BUY:  red close >= swing_l1 -> enter count
        trigger_count = (bull and cur_c <= swing1) if not is_buy else (not bull and cur_c >= swing1)

        if broke_out:
            sw_info  = find_swing(rates)
            new_sw   = sw_info["price"] if sw_info else None
            if new_sw:
                s1_found = (has_s1(rates) or has_s3(rates) or
                            _has_opposite_order_near(order_side, new_sw))
                st["swing_h1"] = new_sw
                st["s1_found"] = s1_found
                st["count"]    = 0

                if not s1_found:
                    # Update TP
                    pending = mt5.orders_get(symbol=SYMBOL)
                    opp_entry = None
                    if pending:
                        opp_limits = [o for o in pending if o.type == opp_lim_type]
                        if opp_limits:
                            opp_entry = opp_limits[0].price_open
                            st["tp_source"] = opp_limits[0].ticket
                    if opp_entry is None:
                        sw_tp = find_swing_tp(rates)
                        opp_entry = sw_tp["price"] if sw_tp else None
                        st["tp_source"] = None
                    if opp_entry and abs(pos.tp - opp_entry) > 0.5 and _tp_valid_for_side(pos_type, pos.price_open, round(opp_entry, 2), 0.01):
                        old_sl = float(pos.sl)
                        old_tp = float(pos.tp)
                        r = mt5.order_send({
                            "action": mt5.TRADE_ACTION_SLTP, "symbol": SYMBOL,
                            "position": ticket, "sl": pos.sl, "tp": round(opp_entry, 2),
                        })
                        ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
                        _audit_sltp_event("S6i:new_swing_tp", pos, old_sl, old_tp, float(pos.sl), round(opp_entry, 2), ok, r)
                        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                            log_event(
                                "TP_CHANGED",
                                "s6i_new_swing_tp",
                                ticket=ticket,
                                side=pos_type,
                                tf=tf_name,
                                old_tp=old_tp,
                                new_tp=round(opp_entry, 2),
                                old_sl=old_sl,
                                new_sl=float(pos.sl),
                            )
                            await _notify_sltp_audit(app, "S6i:new_swing_tp", pos, old_sl, old_tp, float(pos.sl), round(opp_entry, 2), True)
                            if _trade_debug_enabled():
                                print(f"🎯 [{now}] S6i {ticket} TP->{opp_entry:.2f} (new swing)")
                    elif opp_entry and not _tp_valid_for_side(pos_type, pos.price_open, round(opp_entry, 2), 0.01):
                        print(f"WARN [{now}] S6i skip invalid TP at new swing ticket={ticket} type={pos_type} entry={pos.price_open:.2f} new_tp={opp_entry:.2f}")

                print(f"🔄 [{now}] S6i {ticket} new swing={new_sw:.2f} s1={s1_found}")
            return

        if trigger_count:
            st["phase"] = "count"
            st["count"] = 1
            print(f"📊 [{now}] S6i {ticket} watch->count")
            return

    # Phase: count -> count 1-5 candles
    elif st["phase"] == "count":
        if cur_time == st["last_bar_time"]:
            return
        st["last_bar_time"] = cur_time
        st["count"] += 1

        prev_h = float(rates[-2]["high"])
        prev_l = float(rates[-2]["low"])

        # SELL: green close > swing_h1 and > prev_high -> breakout -> restart
        # BUY:  red close < swing_l1 and < prev_low  -> breakout -> restart
        if not is_buy:
            breakout = bull and cur_c > swing1 and cur_c > prev_h
        else:
            breakout = not bull and cur_c < swing1 and cur_c < prev_l

        if breakout:
            sw_info = find_swing(rates)
            new_sw  = sw_info["price"] if sw_info else None
            if new_sw:
                s1_found = (has_s1(rates) or has_s3(rates) or
                            _has_opposite_order_near(order_side, new_sw))
                st["swing_h1"] = new_sw
                st["s1_found"] = s1_found
                st["phase"]    = "watch"
                st["count"]    = 0
                print(f"🔄 [{now}] S6i {ticket} count->watch new swing={new_sw:.2f}")
            return

        # Reached 5 candles -> look for swing2
        if st["count"] >= 5:
            sw2_info = find_swing(rates)
            if not is_buy:
                swing2 = sw2_info["price"] if sw2_info and sw2_info["price"] > swing1 + 0.5 else None
            else:
                swing2 = sw2_info["price"] if sw2_info and sw2_info["price"] < swing1 - 0.5 else None

            if swing2:
                await _s6i_on_swing2(app, pos, pos_type, rates, st, swing1, swing2,
                                     now, sig_e, tf_name, ticket, is_buy,
                                     has_s1, has_s3, order_side, our_lim_type,
                                     find_swing_tp)
            else:
                st["phase"] = "wait_swing2"
                print(f"INFO [{now}] S6i {ticket} reached 5 candles without swing2 -> wait")

    # Phase: wait_swing2 -> wait for the second swing
    elif st["phase"] == "wait_swing2":
        if cur_time == st["last_bar_time"]:
            return
        st["last_bar_time"] = cur_time

        sw2_info = find_swing(rates)
        if not is_buy:
            swing2 = sw2_info["price"] if sw2_info and sw2_info["price"] > swing1 + 0.5 else None
        else:
            swing2 = sw2_info["price"] if sw2_info and sw2_info["price"] < swing1 - 0.5 else None

        if swing2:
            await _s6i_on_swing2(app, pos, pos_type, rates, st, swing1, swing2,
                                 now, sig_e, tf_name, ticket, is_buy,
                                 has_s1, has_s3, order_side, our_lim_type,
                                 find_swing_tp)

    # Phase: order_placed -> monitor the placed SELL/BUY limit
    elif st["phase"] == "order_placed":
        order_ticket = st.get("order_ticket")
        swing2       = st.get("swing_h2")
        if not order_ticket:
            _s6i_state.pop(ticket, None)
            return

        # Does the order still exist?
        orders = mt5.orders_get(symbol=SYMBOL)
        order_exists = orders and any(o.ticket == order_ticket for o in orders)
        if not order_exists:
            _s6i_state.pop(ticket, None)
            print(f"OK [{now}] S6i {ticket} order {order_ticket} filled/cancelled -> done")
            return

        # Engulf through swing2 -> cancel the order
        if swing2:
            cancel = (bull and cur_c > swing2) if not is_buy else (not bull and cur_c < swing2)
            if cancel:
                r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": order_ticket})
                if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                    _s6i_state.pop(ticket, None)
                    await tg(app, (f"❌ *S6i ยกเลิก - กลืนกิน swing2*\n"
                              f"📝 Order:`{order_ticket}` ยกเลิก"))
                    print(f"❌ [{now}] S6i cancel {order_ticket} engulf swing2")


async def _s6i_on_swing2(app, pos, pos_type, rates, st, swing1, swing2,
                         now, sig_e, tf_name, ticket, is_buy,
                         has_s1, has_s3, order_side, our_lim_type,
                         find_swing_tp):
    """Handle swing 2: check S1/S3 pattern, then place an order or keep waiting."""
    st["swing_h2"] = swing2
    s1_at_2 = (has_s1(rates) or has_s3(rates) or
               _has_opposite_order_near(order_side, swing2))

    if s1_at_2:
        # S1/S3 found at swing2 -> wait for the normal limit and set TP from opposite limit
        opp_lim_type = mt5.ORDER_TYPE_SELL_LIMIT if is_buy else mt5.ORDER_TYPE_BUY_LIMIT
        pending = mt5.orders_get(symbol=SYMBOL)
        opp_entry = None
        if pending:
            opp_limits = [o for o in pending if o.type == opp_lim_type]
            if opp_limits:
                opp_entry = opp_limits[0].price_open
                st["tp_source"] = opp_limits[0].ticket
        if opp_entry is None:
            sw_tp = find_swing_tp(rates)
            opp_entry = sw_tp["price"] if sw_tp else None
            st["tp_source"] = None

        if opp_entry and abs(pos.tp - opp_entry) > 0.5 and _tp_valid_for_side(pos_type, pos.price_open, round(opp_entry, 2), 0.01):
            old_sl = float(pos.sl)
            old_tp = float(pos.tp)
            r = mt5.order_send({
                "action": mt5.TRADE_ACTION_SLTP, "symbol": SYMBOL,
                "position": ticket, "sl": pos.sl, "tp": round(opp_entry, 2),
            })
            ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
            _audit_sltp_event("S6i:swing2_tp", pos, old_sl, old_tp, float(pos.sl), round(opp_entry, 2), ok, r)
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                log_event(
                    "TP_CHANGED",
                    "s6i_swing2_tp",
                    ticket=ticket,
                    side=pos_type,
                    tf=tf_name,
                    old_tp=old_tp,
                    new_tp=round(opp_entry, 2),
                    old_sl=old_sl,
                    new_sl=float(pos.sl),
                )
                await _notify_sltp_audit(app, "S6i:swing2_tp", pos, old_sl, old_tp, float(pos.sl), round(opp_entry, 2), True)
                if _trade_debug_enabled():
                    print(f"🎯 [{now}] S6i {ticket} TP->{opp_entry:.2f} (S1/S3 at swing2)")
        elif opp_entry and not _tp_valid_for_side(pos_type, pos.price_open, round(opp_entry, 2), 0.01):
            print(f"WARN [{now}] S6i skip invalid TP at swing2 ticket={ticket} type={pos_type} entry={pos.price_open:.2f} new_tp={opp_entry:.2f}")

        st["phase"] = "watch"
        st["swing_h1"] = swing2
        st["count"] = 0
        print(f"OK [{now}] S6i {ticket} swing2={swing2:.2f} S1/S3 found -> keep watching")
    else:
        # No S1/S3 -> place a limit order at swing1
        sw_tp_info = find_swing_tp(rates)
        tp_price   = sw_tp_info["price"] if sw_tp_info else None
        if not tp_price:
            print(f"WARN [{now}] S6i {ticket} no swing TP found -> skip")
            _s6i_state.pop(ticket, None)
            return

        # SELL: SL = swing_h2 + 100pt | BUY: SL = swing_l2 - 100pt
        sl_price = round(swing2 + 1.0, 2) if not is_buy else round(swing2 - 1.0, 2)
        vol      = SYMBOL_CONFIG[SYMBOL]["volume"]

        r = mt5.order_send({
            "action":       mt5.TRADE_ACTION_PENDING,
            "symbol":       SYMBOL,
            "volume":       vol,
            "type":         our_lim_type,
            "price":        round(swing1, 2),
            "sl":           sl_price,
            "tp":           round(tp_price, 2),
            "deviation":    20,
            "magic":        0,
            "comment":      f"{tf_name}_S6i_{pos_type.lower()}",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": _get_filling_mode(),
        })
        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
            st["order_ticket"] = r.order
            st["phase"]        = "order_placed"
            side_label = "SELL" if not is_buy else "BUY"
            swing_label = f"H1:`{swing1:.2f}` H2:`{swing2:.2f}`" if not is_buy \
                          else f"L1:`{swing1:.2f}` L2:`{swing2:.2f}`"
            await tg(app, (f"📌 *S6i {side_label} LIMIT*\n"
                      f"{sig_e} [{tf_name}] Ticket:`{ticket}`\n"
                      f"📌 Entry:`{swing1:.2f}` SL:`{sl_price:.2f}` TP:`{tp_price:.2f}`\n"
                      f"Swing {swing_label}\n"
                      f"📝 Order:`{r.order}`"))
            print(f"📌 [{now}] S6i {side_label} LIMIT at {swing1:.2f} SL={sl_price} TP={tp_price}")
        else:
            retcode = r.retcode if r else "None"
            print(f"❌ [{now}] S6i order FAIL retcode={retcode}")
            _s6i_state.pop(ticket, None)


async def check_s6_trail(app):
    """
    Strategy 6 - 2 High 2 Low Trail SL.
    - Original S6: continues from positions opened by strategy 2/3
    - S6i: scans swings and places new orders for positions with entry done
    Both modes can run together.
    """
    from strategy1 import strategy_1

    s6_on  = active_strategies.get(6, False)
    s6i_on = active_strategies.get(7, False)

    if not s6_on and not s6i_on:
        return

    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        _s6_state.clear()
        _s6i_state.clear()
        return

    open_tickets = {p.ticket for p in positions}
    for t in list(_s6_state.keys()):
        if t not in open_tickets:
            _s6_state.pop(t, None)
    for t in list(_s6i_state.keys()):
        if t not in open_tickets:
            _s6i_state.pop(t, None)

    now = now_bkk().strftime("%H:%M:%S")

    for pos in positions:
        ticket   = pos.ticket
        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        sid      = position_sid.get(ticket)
        state    = _entry_state.get(ticket)

        if state != "done":
            continue

        # Original S6: only sid 2/3
        if s6_on and sid in (2, 3):
            if _trade_debug_enabled():
                print(f"[{now}] 🔍 S6: {pos_type} {ticket} sid={sid}")
            await _s6_process_ticket(app, pos, positions, _s6_state, "S6", now,
                                     _get_s6_prev_swing_high, _get_s6_prev_swing_low, strategy_1)

        # S6i: every position not already tracked by original S6
        if s6i_on and ticket not in _s6_state:
            if _trade_debug_enabled():
                print(f"[{now}] 🔍 S6i: {pos_type} {ticket} sid={sid}")
            await _s6i_process_ticket(app, pos, now,
                                      _get_s6_prev_swing_high, _get_s6_prev_swing_low)


def _pdfiboplus_in_zone(order_price: float, signal: str, h: float, l: float,
                     sid: int = 0, gap_bot: float = 0.0, gap_top: float = 0.0) -> bool:
    """True ถ้า order_price อยู่ใน zone ที่ถูกต้อง (Fibonacci 38.2/61.8)

    Discount (BUY zone)  → price < L + range*0.382  (ต่ำกว่า 38.2%)
    Premium  (SELL zone) → price > L + range*0.618  (สูงกว่า 61.8%)
    Middle zone (38.2%–61.8%) → ถือว่าผิดฝั่ง

    S2 พิเศษ: ถ้า gap มีบางส่วนอยู่ใน zone ที่ถูกต้องให้ PASS
      BUY:  gap_bot < fib_382 → gap คร่อม Discount zone
      SELL: gap_top > fib_618 → gap คร่อม Premium zone
    """
    if h <= l:
        return True  # invalid range → pass
    _range   = h - l
    fib_382  = l + _range * 0.382
    fib_618  = l + _range * 0.618
    if sid == 2 and gap_bot > 0 and gap_top > 0 and gap_top > gap_bot:
        if signal == "BUY" and gap_bot < fib_382:
            return True   # gap_bot อยู่ใน Discount zone (< 38.2%)
        if signal == "SELL" and gap_top > fib_618:
            return True   # gap_top อยู่ใน Premium zone (> 61.8%)
        # gap คร่อม H หรือ L แต่ไม่คร่อม zone boundary → PASS
        if signal == "BUY" and gap_top > h and gap_bot >= fib_382:
            return True   # gap คร่อม H ไม่คร่อม 38.2% boundary
        if signal == "SELL" and gap_bot < l and gap_top <= fib_618:
            return True   # gap คร่อม L ไม่คร่อม 61.8% boundary
    if signal == "BUY":
        return order_price < fib_382   # Discount zone: below 38.2%
    elif signal == "SELL":
        return order_price > fib_618   # Premium zone: above 61.8%
    return True


def _pdfiboplus_process(ticket: int, order, info: dict, combined: bool = False) -> tuple:
    """Premium/Discount zone recheck per ticket — 2 รอบ
    เรียกจาก check_cancel_pending_orders ทุก cycle
    Return (status: str, tg_msgs: list[str])
      status: "pass" | "fail" | "wait"

    รอบที่ 1 : เมื่อ order เกิด
      - แบบแยก (combined=False): fail → คืน "fail" ทันที, pass → รอรอบ 2
      - แบบรวม (combined=True) : ผลเก็บไว้ คืน "wait" เสมอ รอรอบ 2 ก่อน
    รอบที่ 2 : H หรือ L เปลี่ยนครั้งแรก — คืน "pass" หรือ "fail" (ทั้ง 2 mode)

    แบบรวม: ครบ 2 รอบ → นับเป็น 1 โหวต ส่งไปรวมกับ RSI + Trend (2/3 voting)
    กฎ (PD Fibo Plus): entry < 38.2% (Discount) → BUY ผ่าน / entry > 61.8% (Premium) → SELL ผ่าน
        ช่วง 38.2%–61.8% (Middle) → ถือว่าผิดฝั่งทั้ง BUY/SELL
    """
    if not getattr(config, "PDFIBOPLUS_ENABLED", False):
        return "wait", []

    # ถ้าผ่าน round2 (pending) แล้ว → skip ไม่ต้องวิ่งซ้ำ
    if ticket in _pdfiboplus_pending_passed:
        return "pass", []

    signal = info.get("signal", "")
    if signal not in ("BUY", "SELL"):
        ot = getattr(order, "type", None)
        signal = "BUY" if ot == mt5.ORDER_TYPE_BUY_LIMIT else "SELL" if ot == mt5.ORDER_TYPE_SELL_LIMIT else ""
    if not signal:
        return "wait", []

    tf          = info.get("tf", "")
    _order_sid  = int(info.get("sid", 0) or 0)
    order_price = float(order.price_open)
    sig_e   = _pending_order_icon(order)
    ot_name = _pending_order_type_name(order)

    # S2 gap boundaries สำหรับ PD zone check พิเศษ
    _s2_gap_bot = float(info.get("final_gap_bot", info.get("gap_bot", 0)) or 0)
    _s2_gap_top = float(info.get("final_gap_top", info.get("gap_top", 0)) or 0)

    from hhll_swing import get_swing_hl_pts
    sh_pt, sl_pt = get_swing_hl_pts(tf)
    if not sh_pt or not sl_pt:
        return "wait", []
    h = float(sh_pt["price"])
    l = float(sl_pt["price"])
    if h <= l:
        return "wait", []

    eq      = (h + l) / 2.0
    _range  = h - l
    fib_382 = round(l + _range * 0.382, 5)
    fib_618 = round(l + _range * 0.618, 5)
    state   = _pdfiboplus_state.get(ticket)
    tg_msgs = []

    def _chk_msg(rnd: int, changed: str, result: bool) -> str:
        _chg = f"{changed} เปลี่ยน | " if changed else ""
        _zone_ok = (signal == "SELL" and order_price > fib_618) or (signal == "BUY" and order_price < fib_382)
        _zone = ("Premium 🔴" if order_price > fib_618 else
                 "Discount 🟢" if order_price < fib_382 else "Middle ⚪")
        _zone_str = f"{_zone} {'✅' if _zone_ok else '❌'}"
        return (
            f"📊 *PD Fibo Plus Check — รอบ {rnd}/2*\n"
            f"{sig_e} {ot_name} [{tf}] `#{ticket}`\n"
            f"{_chg}38.2%: `{fib_382}` | 61.8%: `{fib_618}`\n"
            f"Entry: `{order_price}` | H: `{h}` | L: `{l}`\n"
            f"Zone: {_zone_str}\n"
            f"ผล: {'✅ PASS' if result else '❌ FAIL'}"
        )

    # ─── S2: ตรวจ case entry นอก zone แต่ gap 50%-98% คร่อม zone ────
    # ถ้าใช่ → ย้าย entry จาก 98% → 50% mark ก่อนเช็ค PD
    _s2_adjusted_entry = 0.0
    _s2_adj_reason     = ""
    if _order_sid == 2 and _s2_gap_bot > 0 and _s2_gap_top > _s2_gap_bot:
        if signal == "BUY":
            # Case 1: gap คร่อม EQ → ย้าย entry มาที่ EQ
            if order_price > eq and _s2_gap_bot < eq:
                _s2_adjusted_entry = round(eq, 2)
                _s2_adj_reason     = "EQ (gap คร่อม EQ)"
            # Case 2: gap คร่อม H แต่ไม่คร่อม EQ → ย้าย entry มาที่ 50% ของ gap
            elif _s2_gap_top > h and _s2_gap_bot >= eq:
                _s2_adjusted_entry = round((_s2_gap_bot + _s2_gap_top) / 2.0, 2)
                _s2_adj_reason     = "50% gap (gap คร่อม H)"
        elif signal == "SELL":
            # Case 1: gap คร่อม EQ → ย้าย entry มาที่ EQ
            if order_price < eq and _s2_gap_top > eq:
                _s2_adjusted_entry = round(eq, 2)
                _s2_adj_reason     = "EQ (gap คร่อม EQ)"
            # Case 2: gap คร่อม L แต่ไม่คร่อม EQ → ย้าย entry มาที่ 50% ของ gap
            elif _s2_gap_bot < l and _s2_gap_top <= eq:
                _s2_adjusted_entry = round((_s2_gap_bot + _s2_gap_top) / 2.0, 2)
                _s2_adj_reason     = "50% gap (gap คร่อม L)"

    # ─── รอบที่ 1: เมื่อ order เกิด — ตัดสินทันที ────────────────────
    if state is None:
        _outside_pd = order_price < l or order_price > h

        # ─── 1-Swing-Back Fallback เมื่อ entry อยู่นอก [L, H] ──────────
        # entry < L → ถอย H ไป 1 swing (ใช้ H เก่ากว่า คือ อีกตัวระหว่าง HH/LH)
        # entry > H → ถอย L ไป 1 swing (ใช้ L เก่ากว่า คือ อีกตัวระหว่าง HL/LL)
        # ถ้า fallback แล้วยังอยู่นอก range → รอรอบ 2 (ไม่ fail รอบ 1)
        _fallback_used  = False
        _wait_round2    = False
        _fb_h, _fb_l    = h, l
        if _outside_pd:
            try:
                from hhll_swing import get_prev_swing_hl_pts
                _prev_sh, _prev_sl = get_prev_swing_hl_pts(tf)
                if order_price < l and _prev_sh is not None:
                    _try_h = float(_prev_sh["price"])
                    if _try_h > _fb_l:
                        _fb_h = _try_h
                        _fallback_used = True
                elif order_price > h and _prev_sl is not None:
                    _try_l = float(_prev_sl["price"])
                    if _fb_h > _try_l:
                        _fb_l = _try_l
                        _fallback_used = True
            except Exception:
                pass

        if _fallback_used:
            _fb_outside = order_price < _fb_l or order_price > _fb_h
            if _fb_outside:
                # fallback แล้วยังอยู่นอก range → รอรอบ 2
                _wait_round2 = True
                result = False   # provisional — ใช้แค่เพื่อ save state; จะ return "wait" ไม่ใช่ "fail"
            else:
                result = _pdfiboplus_in_zone(order_price, signal, _fb_h, _fb_l,
                                          sid=_order_sid, gap_bot=_s2_gap_bot, gap_top=_s2_gap_top)
        else:
            result = _pdfiboplus_in_zone(order_price, signal, h, l,
                                      sid=_order_sid, gap_bot=_s2_gap_bot, gap_top=_s2_gap_top)

        # S2 entry adjustment: ย้าย entry → 50% mark เมื่อ PASS via gap rule
        if result and _s2_adjusted_entry > 0:
            _ok_mod, _ = _modify_pending_entry(order, _s2_adjusted_entry)
            if _ok_mod:
                _pend = pending_order_tf.get(ticket)
                if isinstance(_pend, dict):
                    _pend["entry"] = _s2_adjusted_entry
                    pending_order_tf[ticket] = _pend
                log_event("S2_ENTRY_ADJUSTED",
                          f"PD zone: entry {order_price} → {_s2_adjusted_entry} ({_s2_adj_reason})",
                          ticket=ticket, tf=tf, signal=signal,
                          old_entry=order_price, new_entry=_s2_adjusted_entry, eq=round(eq, 2))
                tg_msgs.append(
                    f"📐 *S2 Entry ปรับ (PD Zone)*\n"
                    f"{sig_e} [{tf}] `#{ticket}`\n"
                    f"Entry: `{order_price}` → `{_s2_adjusted_entry}` ({_s2_adj_reason})\n"
                    f"EQ: `{round(eq,2)}` | Gap: `{_s2_gap_bot}`–`{_s2_gap_top}`"
                )
        _pdfiboplus_state[ticket] = {
            "signal": signal, "tf": tf, "price": order_price,
            "cur_h": h, "cur_l": l,
            "round1": 0 if _wait_round2 else (1 if result else -1),
            "outside_pd": _outside_pd,
        }
        state = _pdfiboplus_state[ticket]

        # ─── กรณี: fallback แล้วยังอยู่นอก range → รอรอบ 2 ────────────
        if _wait_round2:
            _fb_eq = round((_fb_h + _fb_l) / 2.0, 5)
            log_event("PDFIBOPLUS", "round1_fallback_wait",
                      ticket=ticket, signal=signal, tf=tf,
                      price=order_price, h=h, l=l,
                      fb_h=_fb_h, fb_l=_fb_l, eq=_fb_eq)
            tg_msgs.append(
                f"📊 *PD Fibo Plus Check — รอบ 1/2 (Fallback)*\n"
                f"{sig_e} {ot_name} [{tf}] `#{ticket}`\n"
                f"Entry: `{order_price}` | นอก [L=`{l}`, H=`{h}`]\n"
                f"Fallback H=`{_fb_h}` / L=`{_fb_l}` → ยังนอก range\n"
                f"⏳ รอรอบ 2 (H/L เปลี่ยน)"
            )
            return "wait", tg_msgs

        # ─── กรณี: ปกติ หรือ fallback แล้วอยู่ใน range ─────────────────
        _eff_h   = _fb_h if _fallback_used else h
        _eff_l   = _fb_l if _fallback_used else l
        _log_eq  = round((_eff_h + _eff_l) / 2.0, 5)
        _fb_note = f"1-swing-back H={_fb_h}/L={_fb_l}" if _fallback_used else ""
        _note    = " | ".join(filter(None, ["outside_pd_range" if _outside_pd else "", _fb_note]))
        log_event("PDFIBOPLUS", "round1",
                  ticket=ticket, signal=signal, tf=tf,
                  price=order_price, h=_eff_h, l=_eff_l, eq=_log_eq,
                  result="PASS" if result else "FAIL",
                  note=_note)
        if _fallback_used:
            _fb_eq = round((_fb_h + _fb_l) / 2.0, 5)
            _chk_note = f"1-swing-back H=`{_fb_h}` L=`{_fb_l}` EQ=`{_fb_eq}`"
        else:
            _chk_note = "outside PD range" if _outside_pd else ""
        tg_msgs.append(_chk_msg(1, _chk_note, result))
        if not result and not combined:
            # แบบแยก: fail ทันที — ไม่ต้องรอรอบ 2
            log_event("PDFIBOPLUS", "fail_round1",
                      ticket=ticket, signal=signal, tf=tf)
            return "fail", tg_msgs
        # แบบรวม: เก็บผลรอบ 1 ไว้ก่อน รอ H/L เปลี่ยนสำหรับรอบ 2 เสมอ
        return "wait", tg_msgs

    # ─── รอบที่ 2: H/L เปลี่ยนครั้งแรก — ตัดสินทันที ────────────────
    h_changed = abs(h - state["cur_h"]) > 0.01
    l_changed = abs(l - state["cur_l"]) > 0.01
    if h_changed or l_changed:
        changed_parts = []
        if h_changed: changed_parts.append("H")
        if l_changed: changed_parts.append("L")
        changed_str = "/".join(changed_parts)

        result = _pdfiboplus_in_zone(order_price, signal, h, l,
                                  sid=_order_sid, gap_bot=_s2_gap_bot, gap_top=_s2_gap_top)
        state["cur_h"] = h
        state["cur_l"] = l
        _pdfiboplus_state[ticket] = state
        log_event("PDFIBOPLUS", "round2",
                  ticket=ticket, signal=signal, tf=tf,
                  price=order_price, h=h, l=l, eq=round(eq, 5),
                  changed=changed_str,
                  result="PASS" if result else "FAIL")
        tg_msgs.append(_chk_msg(2, changed_str, result))
        if result:
            _pdfiboplus_state.pop(ticket, None)
            _pdfiboplus_pending_passed.add(ticket)  # ป้องกัน round1 วิ่งซ้ำหลัง round2 PASS
            log_event("PDFIBOPLUS", "pass",
                      ticket=ticket, signal=signal, tf=tf)
            return "pass", tg_msgs
        log_event("PDFIBOPLUS", "fail_round2",
                  ticket=ticket, signal=signal, tf=tf)
        return "fail", tg_msgs

    return "wait", tg_msgs  # รอ H/L เปลี่ยน


async def check_cancel_pending_orders(app):
    """
    Auto cancel limit orders when setup is no longer valid:
    BUY LIMIT:  price closes above the main swing high of that TF -> remove it
    SELL LIMIT: price closes below the main swing low of that TF  -> remove it

    Main swing high/low means max/min from the TF lookback window.
    """
    orders = mt5.orders_get(symbol=SYMBOL)
    if not orders:
        pending_order_tf.clear()
        _pdfiboplus_state.clear()
        _pdfiboplus_pending_passed.clear()
        _triple_check_state.clear()
        return

    now = now_bkk().strftime("%H:%M:%S")
    open_tickets = {o.ticket for o in orders}
    # tickets ที่กลายเป็น position แล้ว (filled) → ไม่ pop position_tf ออก
    _open_pos_tickets = {p.ticket for p in (mt5.positions_get(symbol=SYMBOL) or [])}

    # Cleanup PD zone state for tickets that no longer exist
    for t in list(_pdfiboplus_state.keys()):
        if t not in open_tickets:
            _pdfiboplus_state.pop(t, None)
    _pdfiboplus_pending_passed.difference_update(
        t for t in list(_pdfiboplus_pending_passed) if t not in open_tickets
    )

    # Cleanup fill-checked set for closed positions
    _pdfiboplus_fill_checked.difference_update(
        t for t in list(_pdfiboplus_fill_checked) if t not in _open_pos_tickets
    )
    for t in list(_pdfiboplus_fill_state.keys()):
        if t not in _open_pos_tickets:
            _pdfiboplus_fill_state.pop(t, None)

    # Cleanup triple check state for tickets that no longer exist
    for t in list(_triple_check_state.keys()):
        if t not in open_tickets:
            _triple_check_state.pop(t, None)

    # Cleanup trend recheck state for positions that no longer exist
    for t in list(_trend_recheck_state.keys()):
        if t not in _open_pos_tickets:
            _trend_recheck_state.pop(t, None)
    _fill_trend_checked.difference_update(
        t for t in list(_fill_trend_checked) if t not in _open_pos_tickets
    )

    # Cleanup pending trend approach state for orders that no longer exist
    for t in list(_pending_trend_approach.keys()):
        if t not in open_tickets and t not in _open_pos_tickets:
            _pending_trend_approach.pop(t, None)

    # Cleanup tickets that no longer exist
    for t in list(pending_order_tf.keys()):
        if t not in open_tickets:
            info = pending_order_tf.pop(t, None)
            # ถ้า fill กลายเป็น position → คง position_tf/sid/pattern ไว้ให้ notify_limit_fills ใช้
            if t not in _open_pos_tickets:
                # หายจาก order list และไม่ใช่ position → ถูก cancel จริง
                position_tf.pop(t, None)
                position_sid.pop(t, None)
                position_pattern.pop(t, None)
                if isinstance(info, dict):
                    log_event(
                        "ORDER_CANCELED",
                        "Pending disappeared from MT5 order list",
                        tf=info.get("tf", ""),
                        sid=info.get("sid", ""),
                        signal=info.get("signal", ""),
                        ticket=t,
                        entry=info.get("entry"),
                        sl=info.get("sl"),
                        tp=info.get("tp"),
                        flow_id=info.get("flow_id", ""),
                        parent_flow_id=info.get("parent_flow_id", ""),
                    )
            elif isinstance(info, dict):
                # order fill แล้ว (กลายเป็น position) → ไม่ใช่ cancel จริง ห้าม log ORDER_CANCELED
                # ถ้า position_tf/pattern ยังไม่มี ให้ restore จาก pending info
                if t not in position_tf and info.get("tf"):
                    position_tf[t] = info["tf"]
                if t not in position_pattern and info.get("pattern"):
                    position_pattern[t] = info["pattern"]
                if t not in position_sid and info.get("sid") is not None:
                    position_sid[t] = info["sid"]

    for order in orders:
        ticket = order.ticket
        info   = pending_order_tf.get(ticket)
        if not info:
            continue
        tf = info.get("tf") if isinstance(info, dict) else info

        # Use the smallest TF (check_tf) for candle quality checks
        # Use the main TF for swing high/low
        check_tf = position_tf.get(ticket) or tf

        tf_val   = TF_OPTIONS.get(tf, mt5.TIMEFRAME_M1)
        lookback = TF_LOOKBACK.get(tf, SWING_LOOKBACK)
        rates    = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, lookback + 6)
        if rates is None or len(rates) < 5:
            continue

        # Main swing high/low = max/min over the full TF lookback
        swing_high = max(float(r["high"]) for r in rates)
        swing_low  = min(float(r["low"])  for r in rates)

        last_close = float(rates[-1]["close"])

        # Candle quality uses check_tf (the smaller TF)
        check_tf_val   = TF_OPTIONS.get(check_tf, mt5.TIMEFRAME_M1)
        check_lookback = min(TF_LOOKBACK.get(check_tf, SWING_LOOKBACK) + 6, 50)
        candle_rates   = mt5.copy_rates_from_pos(SYMBOL, check_tf_val, 1, check_lookback)
        if candle_rates is None:
            candle_rates = rates

        should_cancel = False
        reason = ""

        # S10 HTF sweep recheck: once the next HTF bar starts, confirm that the original sweep bar is still valid
        if (
            isinstance(info, dict)
            and info.get("sid") == 10
            and not info.get("s10_sweep_checked")
            and info.get("s10_htf_tf")
            and info.get("s10_parent_time")
            and info.get("s10_sweep_time")
        ):
            from strategy10 import is_s10_htf_sweep_valid

            s10_htf_tf = info.get("s10_htf_tf") or tf
            s10_tf_val = TF_OPTIONS.get(s10_htf_tf, tf_val)
            s10_cur_bar = mt5.copy_rates_from_pos(SYMBOL, s10_tf_val, 0, 1)
            if s10_cur_bar is not None and len(s10_cur_bar) > 0:
                s10_cur_open = int(s10_cur_bar[0]["time"])
                s10_sweep_time = int(info.get("s10_sweep_time", 0) or 0)
                if s10_cur_open > s10_sweep_time:
                    s10_rates = mt5.copy_rates_from_pos(SYMBOL, s10_tf_val, 1, max(TF_LOOKBACK.get(s10_htf_tf, SWING_LOOKBACK) + 6, 50))
                    if s10_rates is not None and len(s10_rates) > 1:
                        parent_bar = next((r for r in s10_rates if int(r["time"]) == int(info.get("s10_parent_time", 0) or 0)), None)
                        sweep_bar = next((r for r in s10_rates if int(r["time"]) == s10_sweep_time), None)
                        if parent_bar is not None and sweep_bar is not None:
                            s10_valid = is_s10_htf_sweep_valid(parent_bar, sweep_bar, info.get("signal", ""), info.get("s10_bar_mode", ""))
                            if not s10_valid:
                                log_event(
                                    "S10_SWEEP_RECHECK",
                                    "FAIL",
                                    ticket=ticket,
                                    tf=tf,
                                    htf_tf=s10_htf_tf,
                                    signal=info.get("signal", ""),
                                    side=info.get("signal", ""),
                                    sweep_time=fmt_mt5_bkk_ts(s10_sweep_time, "%H:%M %d-%b-%Y"),
                                    parent_time=fmt_mt5_bkk_ts(int(info.get("s10_parent_time", 0) or 0), "%H:%M %d-%b-%Y"),
                                )
                                should_cancel = True
                                reason = (
                                    f"S10 Sweep Recheck [{s10_htf_tf}]: sweep bar "
                                    f"{fmt_mt5_bkk_ts(s10_sweep_time, '%H:%M %d-%b-%Y')} is no longer a valid sweep"
                                )
                            else:
                                info["s10_sweep_checked"] = True
                                pending_order_tf[ticket] = info
                                save_runtime_state()
                                log_event(
                                    "S10_SWEEP_RECHECK",
                                    "PASS",
                                    ticket=ticket,
                                    tf=tf,
                                    htf_tf=s10_htf_tf,
                                    signal=info.get("signal", ""),
                                    side=info.get("signal", ""),
                                    sweep_time=fmt_mt5_bkk_ts(s10_sweep_time, "%H:%M %d-%b-%Y"),
                                    parent_time=fmt_mt5_bkk_ts(int(info.get("s10_parent_time", 0) or 0), "%H:%M %d-%b-%Y"),
                                )

        # S10 ongoing HTF structure-break check (ทำงานหลัง s10_sweep_checked=True)
        # ถ้าแท่ง HTF ที่ปิดแล้วหลัง sweep bar ปิด break parent low (BUY) / parent high (SELL)
        # → CRT pattern invalid → ยกเลิก pending ทันที
        if (
            not should_cancel
            and isinstance(info, dict)
            and info.get("sid") == 10
            and info.get("s10_sweep_checked")   # ← initial recheck ผ่านแล้ว
            and info.get("s10_htf_tf")
            and info.get("s10_sweep_time")
        ):
            _sb_htf    = info.get("s10_htf_tf") or tf
            _sb_tf_val = TF_OPTIONS.get(_sb_htf, tf_val)
            _sb_sweep_ts = int(info.get("s10_sweep_time", 0) or 0)
            # ใช้ sweep_low/high ถ้ามี (fallback → parent_low/high)
            _sb_p_low    = float(info.get("s10_parent_low",  0) or 0)
            _sb_p_high   = float(info.get("s10_parent_high", 0) or 0)
            _sb_s_low    = float(info.get("s10_sweep_low",   0) or 0) or _sb_p_low
            _sb_s_high   = float(info.get("s10_sweep_high",  0) or 0) or _sb_p_high
            _sb_sig      = info.get("signal", "")
            if _sb_sig in ("BUY", "SELL") and (_sb_s_low > 0 or _sb_s_high > 0):
                _sb_n = max(TF_LOOKBACK.get(_sb_htf, SWING_LOOKBACK) + 6, 50)
                _sb_rates = mt5.copy_rates_from_pos(SYMBOL, _sb_tf_val, 1, _sb_n)
                if _sb_rates is not None and len(_sb_rates) > 0:
                    _bars_post_sweep = [r for r in _sb_rates if int(r["time"]) > _sb_sweep_ts]
                    if _bars_post_sweep:
                        _sb_broken = False
                        if _sb_sig == "BUY" and _sb_s_low > 0:
                            # แท่ง HTF ปิดต่ำกว่า sweep low → structure พัง → invalid
                            _sb_broken = any(float(r["close"]) < _sb_s_low for r in _bars_post_sweep)
                        elif _sb_sig == "SELL" and _sb_s_high > 0:
                            # แท่ง HTF ปิดสูงกว่า sweep high → structure พัง → invalid
                            _sb_broken = any(float(r["close"]) > _sb_s_high for r in _bars_post_sweep)
                        if _sb_broken:
                            _sb_dir  = "low" if _sb_sig == "BUY" else "high"
                            _sb_lvl  = _sb_s_low if _sb_sig == "BUY" else _sb_s_high
                            should_cancel = True
                            reason = (
                                f"S10 HTF Structure Break [{_sb_htf}]: "
                                f"แท่งหลัง sweep ปิด break sweep {_sb_dir}={_sb_lvl:.2f} — "
                                f"CRT pattern invalid"
                            )
                            log_event(
                                "S10_STRUCTURE_BREAK",
                                "CANCEL",
                                ticket=ticket, tf=tf, htf_tf=_sb_htf,
                                signal=_sb_sig,
                                sweep_low=_sb_s_low, sweep_high=_sb_s_high,
                                parent_low=_sb_p_low, parent_high=_sb_p_high,
                                sweep_time=fmt_mt5_bkk_ts(_sb_sweep_ts, "%H:%M %d-%b-%Y"),
                            )

        # S10 pending invalidation: if SELL has already touched parent low before fill, cancel immediately
        if (
            not should_cancel
            and isinstance(info, dict)
            and info.get("sid") == 10
            and str(info.get("signal", "")).upper() == "SELL"
            and float(info.get("s10_parent_low", 0.0) or 0.0) > 0.0
        ):
            s10_parent_low = float(info.get("s10_parent_low", 0.0) or 0.0)
            s10_parent_time = int(info.get("s10_parent_time", 0) or 0)
            mon_tf = str(info.get("tf") or tf or "M1")
            mon_tf_val = TF_OPTIONS.get(mon_tf, mt5.TIMEFRAME_M1)
            mon_tf_secs = max(1, _get_tf_seconds(mon_tf_val))
            # คำนวณ parent bar close time (open + HTF period) เพื่อข้าม M1 ภายใน parent bar เอง
            _s10_htf_name_sell = str(info.get("s10_htf_tf") or tf)
            _s10_htf_secs_sell = max(1, _get_tf_seconds(TF_OPTIONS.get(_s10_htf_name_sell, mt5.TIMEFRAME_H1)))
            s10_parent_close = s10_parent_time + _s10_htf_secs_sell
            now_ref_ts = int(candle_rates[-1]["time"]) if candle_rates is not None and len(candle_rates) > 0 else int(time.time())
            bars_needed = max(10, min(500, int((max(0, now_ref_ts - s10_parent_close) // mon_tf_secs) + 10)))
            mon_rates = mt5.copy_rates_from_pos(SYMBOL, mon_tf_val, 0, bars_needed)
            touched_bar = None
            if mon_rates is not None and len(mon_rates) > 0:
                for _bar in mon_rates:
                    if int(_bar["time"]) < s10_parent_close:  # ข้าม M1 ภายใน parent bar
                        continue
                    if float(_bar["low"]) <= s10_parent_low:
                        touched_bar = _bar
                        break
            tick = mt5.symbol_info_tick(SYMBOL)
            cur_bid = float(getattr(tick, "bid", 0.0) or 0.0) if tick else 0.0
            if touched_bar is not None or (cur_bid > 0 and cur_bid <= s10_parent_low):
                touched_txt = ""
                if touched_bar is not None:
                    touched_txt = (
                        f" @ {fmt_mt5_bkk_ts(int(touched_bar['time']), '%H:%M %d-%b-%Y')} "
                        f"(L:{float(touched_bar['low']):.2f})"
                    )
                elif cur_bid > 0:
                    touched_txt = f" @ now (Bid:{cur_bid:.2f})"
                should_cancel = True
                reason = (
                    f"S10 Parent Low Touch Cancel [{info.get('s10_htf_tf', tf)}->{mon_tf}]: "
                    f"SELL pending touched parent low {s10_parent_low:.2f} before fill{touched_txt}"
                )

        # S10 pending invalidation: if BUY has already touched parent high before fill, cancel immediately
        if (
            not should_cancel
            and isinstance(info, dict)
            and info.get("sid") == 10
            and str(info.get("signal", "")).upper() == "BUY"
            and float(info.get("s10_parent_high", 0.0) or 0.0) > 0.0
        ):
            s10_parent_high = float(info.get("s10_parent_high", 0.0) or 0.0)
            s10_parent_time = int(info.get("s10_parent_time", 0) or 0)
            mon_tf = str(info.get("tf") or tf or "M1")
            mon_tf_val = TF_OPTIONS.get(mon_tf, mt5.TIMEFRAME_M1)
            mon_tf_secs = max(1, _get_tf_seconds(mon_tf_val))
            # คำนวณ parent bar close time (open + HTF period) เพื่อข้าม M1 ภายใน parent bar เอง
            _s10_htf_name_buy = str(info.get("s10_htf_tf") or tf)
            _s10_htf_secs_buy = max(1, _get_tf_seconds(TF_OPTIONS.get(_s10_htf_name_buy, mt5.TIMEFRAME_H1)))
            s10_parent_close = s10_parent_time + _s10_htf_secs_buy
            now_ref_ts = int(candle_rates[-1]["time"]) if candle_rates is not None and len(candle_rates) > 0 else int(time.time())
            bars_needed = max(10, min(500, int((max(0, now_ref_ts - s10_parent_close) // mon_tf_secs) + 10)))
            mon_rates = mt5.copy_rates_from_pos(SYMBOL, mon_tf_val, 0, bars_needed)
            touched_bar = None
            if mon_rates is not None and len(mon_rates) > 0:
                for _bar in mon_rates:
                    if int(_bar["time"]) < s10_parent_close:  # ข้าม M1 ภายใน parent bar
                        continue
                    if float(_bar["high"]) >= s10_parent_high:
                        touched_bar = _bar
                        break
            tick = mt5.symbol_info_tick(SYMBOL)
            cur_ask = float(getattr(tick, "ask", 0.0) or 0.0) if tick else 0.0
            if touched_bar is not None or (cur_ask > 0 and cur_ask >= s10_parent_high):
                touched_txt = ""
                if touched_bar is not None:
                    touched_txt = (
                        f" @ {fmt_mt5_bkk_ts(int(touched_bar['time']), '%H:%M %d-%b-%Y')} "
                        f"(H:{float(touched_bar['high']):.2f})"
                    )
                elif cur_ask > 0:
                    touched_txt = f" @ now (Ask:{cur_ask:.2f})"
                should_cancel = True
                reason = (
                    f"S10 Parent High Touch Cancel [{info.get('s10_htf_tf', tf)}->{mon_tf}]: "
                    f"BUY pending touched parent high {s10_parent_high:.2f} before fill{touched_txt}"
                )

        _order_sid = info.get("sid") if isinstance(info, dict) else None

        # Limit TP/SL Break Cancel: cancel when a confirmed candle breaks TP/SL on the selected TF
        # Skip S2 pattern 1 (green engulfing / red engulfing) by design
        # Skip S10 (CRT TBS) — managed by parent touch cancel instead
        _skip_break = (
            _order_sid == 10
            or (
                isinstance(info, dict)
                and info.get("sid") == 2
                and info.get("c3_type") in ("เขียวกลืนกิน", "แดงกลืนกิน")
            )
        )
        if (
            not should_cancel
            and not _skip_break
            and config.LIMIT_BREAK_CANCEL
            and config.LIMIT_BREAK_CANCEL_TF.get(tf, False)
            and len(rates) >= 2
        ):
            cur_bar = rates[-1]
            prev_bar = rates[-2]
            limit_tp = float(order.tp or 0.0)
            limit_sl = float(order.sl or 0.0)
            if not limit_sl and isinstance(info, dict):
                limit_sl = float(info.get("intended_sl", 0.0) or 0.0)

            if order.type == mt5.ORDER_TYPE_BUY_LIMIT:
                if limit_tp > 0 and _is_green_engulf_break(cur_bar, prev_bar, limit_tp):
                    should_cancel = True
                    reason = (
                        f"TP Break Cancel [{tf}]: BUY LIMIT got a confirmed green break above TP "
                        f"close:{_bar_close(cur_bar):.2f} > TP:{limit_tp:.2f} "
                        f"& engulf High[prev]:{_bar_high(prev_bar):.2f}"
                    )
                elif limit_sl > 0 and _is_red_engulf_break(cur_bar, prev_bar, limit_sl):
                    should_cancel = True
                    reason = (
                        f"SL Break Cancel [{tf}]: BUY LIMIT got a confirmed red break below SL "
                        f"close:{_bar_close(cur_bar):.2f} < SL:{limit_sl:.2f} "
                        f"& engulf Low[prev]:{_bar_low(prev_bar):.2f}"
                    )

            elif order.type == mt5.ORDER_TYPE_SELL_LIMIT:
                if limit_tp > 0 and _is_red_engulf_break(cur_bar, prev_bar, limit_tp):
                    should_cancel = True
                    reason = (
                        f"TP Break Cancel [{tf}]: SELL LIMIT got a confirmed red break below TP "
                        f"close:{_bar_close(cur_bar):.2f} < TP:{limit_tp:.2f} "
                        f"& engulf Low[prev]:{_bar_low(prev_bar):.2f}"
                    )
                elif limit_sl > 0 and _is_green_engulf_break(cur_bar, prev_bar, limit_sl):
                    should_cancel = True
                    reason = (
                        f"SL Break Cancel [{tf}]: SELL LIMIT got a confirmed green break above SL "
                        f"close:{_bar_close(cur_bar):.2f} > SL:{limit_sl:.2f} "
                        f"& engulf High[prev]:{_bar_high(prev_bar):.2f}"
                    )

        # Limit Guard: cancel limits whose entry is too far from an existing open position
        # S15 (VP) วาง limit ที่ POC/VAL/VAH ซึ่งอาจไกลจาก position โดยตั้งใจ (รอราคาย้อนมา) → skip
        if not should_cancel and config.LIMIT_GUARD and _order_sid not in (10, 12, 13, 15, 16, 17, 18, 19):
            limit_tf = info.get("tf") if isinstance(info, dict) else info
            positions = mt5.positions_get(symbol=SYMBOL)
            tf_separate = config.LIMIT_GUARD_TF_MODE == "separate"
            if positions and (limit_tf or not tf_separate):
                sym_info = mt5.symbol_info(SYMBOL)
                pt = sym_info.point if sym_info else 0.01
                guard_dist = config.LIMIT_GUARD_POINTS * pt * config.points_scale()  # BTC = 4ร— (background)

                if order.type == mt5.ORDER_TYPE_BUY_LIMIT:
                    for pos in positions:
                        if pos.type != mt5.ORDER_TYPE_BUY:
                            continue
                        if tf_separate:
                            pos_tf = position_tf.get(pos.ticket)
                            if pos_tf != limit_tf:
                                continue
                        pos_entry = pos.price_open
                        limit_entry = order.price_open
                        tick = mt5.symbol_info_tick(SYMBOL)
                        bid = tick.bid if tick else 0
                        if limit_entry > pos_entry and bid > pos_entry + guard_dist:
                            matched_tf = position_tf.get(pos.ticket, "?")
                            should_cancel = True
                            reason = (f"Limit Guard [{limit_tf}->{matched_tf}]: BUY LIMIT {limit_entry:.2f} > "
                                      f"BUY pos {pos_entry:.2f} "
                                      f"& bid {bid:.2f} > {pos_entry + guard_dist:.2f} (+{config.LIMIT_GUARD_POINTS}pt)")
                            break

                elif order.type == mt5.ORDER_TYPE_SELL_LIMIT:
                    for pos in positions:
                        if pos.type != mt5.ORDER_TYPE_SELL:
                            continue
                        if tf_separate:
                            pos_tf = position_tf.get(pos.ticket)
                            if pos_tf != limit_tf:
                                continue
                        pos_entry = pos.price_open
                        limit_entry = order.price_open
                        tick = mt5.symbol_info_tick(SYMBOL)
                        ask = tick.ask if tick else 0
                        if limit_entry < pos_entry and ask < pos_entry - guard_dist:
                            matched_tf = position_tf.get(pos.ticket, "?")
                            should_cancel = True
                            reason = (f"Limit Guard [{limit_tf}->{matched_tf}]: SELL LIMIT {limit_entry:.2f} < "
                                      f"SELL pos {pos_entry:.2f} "
                                      f"& ask {ask:.2f} < {pos_entry - guard_dist:.2f} (-{config.LIMIT_GUARD_POINTS}pt)")
                            break

        # Near Approach Cancel: cancel limit when price gets near entry then pulls away
        if not should_cancel and config.NEAR_APPROACH_CANCEL_ENABLED and _order_sid not in (10, 16):
            _nac_sym = mt5.symbol_info(SYMBOL)
            if _nac_sym:
                _pt = _nac_sym.point or 0.01
                _approach_dist = config.NEAR_APPROACH_CANCEL_POINTS * _pt * config.points_scale()
                _nac_entry = order.price_open
                _nac_lb = max(2, config.NEAR_APPROACH_CANCEL_LOOKBACK)
                _nac_bars = list(rates[-_nac_lb:]) if len(rates) >= _nac_lb else list(rates)
                if len(_nac_bars) >= 2:
                    _last_bar = _nac_bars[-1]
                    _prev_bars = _nac_bars[:-1]
                    if order.type == mt5.ORDER_TYPE_SELL_LIMIT:
                        _threshold = _nac_entry - _approach_dist
                        if (any(float(b["high"]) >= _threshold for b in _prev_bars)
                                and float(_last_bar["high"]) < _threshold):
                            _peak = max(float(b["high"]) for b in _prev_bars)
                            _dist_pt = round((_nac_entry - _peak) / _pt)
                            should_cancel = True
                            reason = (
                                f"Near Approach Cancel [{tf}]: SELL LIMIT {_nac_entry:.2f} "
                                f"high moved within {_dist_pt}pt then pulled back"
                            )
                    elif order.type == mt5.ORDER_TYPE_BUY_LIMIT:
                        _threshold = _nac_entry + _approach_dist
                        if (any(float(b["low"]) <= _threshold for b in _prev_bars)
                                and float(_last_bar["low"]) > _threshold):
                            _valley = min(float(b["low"]) for b in _prev_bars)
                            _dist_pt = round((_valley - _nac_entry) / _pt)
                            should_cancel = True
                            reason = (
                                f"Near Approach Cancel [{tf}]: BUY LIMIT {_nac_entry:.2f} "
                                f"low moved within {_dist_pt}pt then pulled back"
                            )

        # SL Guard: cancel near pending when guard is active for this TF/side
        if not should_cancel and config.SL_GUARD_ENABLED:
            _sg_side = None
            if order.type == mt5.ORDER_TYPE_BUY_LIMIT:
                _sg_side = "BUY"
            elif order.type == mt5.ORDER_TYPE_SELL_LIMIT:
                _sg_side = "SELL"
            if _sg_side and tf:
                _sg_key = (order.symbol.upper(), tf, _sg_side)
                _sg = _sl_guard_state.get(_sg_key, {})
                if _sg.get("active"):
                    # Initialize swing_ref if not yet set (first time we see this active guard)
                    if not _sg.get("swing_ref"):
                        if _sg_side == "BUY":
                            _sg["swing_ref"] = float(min(float(r["low"]) for r in rates))
                        else:
                            _sg["swing_ref"] = float(max(float(r["high"]) for r in rates))
                        _sl_guard_state[_sg_key] = _sg
                    # Check unblock first — new swing formed after block?
                    _sl_guard_check_unblock(tf, _sg_side, rates)
                    _sg = _sl_guard_state.get(_sg_key, {})
                if _sg.get("active"):
                    # Cancel if price is within SL_GUARD_NEAR_POINTS of pending entry
                    _sg_sym = mt5.symbol_info(SYMBOL)
                    _sg_tick = mt5.symbol_info_tick(SYMBOL)
                    if _sg_sym and _sg_tick:
                        _sg_pt = _sg_sym.point or 0.01
                        _sg_near = config.SL_GUARD_NEAR_POINTS * _sg_pt * config.points_scale()
                        _sg_entry = order.price_open
                        _sg_cur = _sg_tick.ask if _sg_side == "BUY" else _sg_tick.bid
                        _sg_dist_pt = abs(_sg_cur - _sg_entry) / _sg_pt
                        if abs(_sg_cur - _sg_entry) <= _sg_near:
                            should_cancel = True
                            reason = (
                                f"SL Guard [{tf}]: {_sg_side} SL hit "
                                f"{_sg.get('count', 0)}x — ยกเลิก pending "
                                f"entry:{_sg_entry:.2f} cur:{_sg_cur:.2f} "
                                f"dist:{_sg_dist_pt:.0f}pt (≤{config.SL_GUARD_NEAR_POINTS}pt)"
                            )

        # SL Guard Combined: cancel near pending when combined guard blocks this TF/side
        if not should_cancel and getattr(config, "SL_GUARD_COMBINED_ENABLED", False):
            _cg_side = None
            if order.type == mt5.ORDER_TYPE_BUY_LIMIT:
                _cg_side = "BUY"
            elif order.type == mt5.ORDER_TYPE_SELL_LIMIT:
                _cg_side = "SELL"
            if _cg_side and tf:
                _cg_tfs = set(getattr(config, "SL_GUARD_COMBINED_TFS", []) or [])
                if not _cg_tfs or tf in _cg_tfs:
                    _cg_sym_key = order.symbol.upper()
                    _cg = _sl_guard_combined.get(_cg_sym_key, {}).get(_cg_side, {})
                    if _cg.get("active") and _cg.get("tf_blocked", {}).get(tf):
                        # เช็คก่อนว่า H/L เกิดแล้วหรือยัง → ถ้าเกิดแล้ว unblock แทน cancel
                        _combined_guard_check_unblock(tf, _cg_side, rates, order.symbol)
                        _cg = _sl_guard_combined.get(_cg_sym_key, {}).get(_cg_side, {})
                        if _cg.get("active") and _cg.get("tf_blocked", {}).get(tf):
                            # H/L ยังไม่เกิด → ถ้าราคาเข้าใกล้ pending ให้ยกเลิก
                            _cg_sym = mt5.symbol_info(SYMBOL)
                            _cg_tick = mt5.symbol_info_tick(SYMBOL)
                            if _cg_sym and _cg_tick:
                                _cg_pt = _cg_sym.point or 0.01
                                _cg_near = config.SL_GUARD_NEAR_POINTS * _cg_pt * config.points_scale()
                                _cg_entry = order.price_open
                                _cg_cur = _cg_tick.ask if _cg_side == "BUY" else _cg_tick.bid
                                _cg_dist_pt = abs(_cg_cur - _cg_entry) / _cg_pt
                                if abs(_cg_cur - _cg_entry) <= _cg_near:
                                    should_cancel = True
                                    reason = (
                                        f"SL Guard Combined [{tf}]: {_cg_side} blocked, H/L ยังไม่เกิด — "
                                        f"ยกเลิก pending entry:{_cg_entry:.2f} cur:{_cg_cur:.2f} "
                                        f"dist:{_cg_dist_pt:.0f}pt (≤{config.SL_GUARD_NEAR_POINTS}pt)"
                                    )

        # SL Guard Group: cancel near pending when group guard blocks this TF/side
        if not should_cancel and getattr(config, "SL_GUARD_GROUP_ENABLED", False):
            _gg_side = None
            if order.type == mt5.ORDER_TYPE_BUY_LIMIT:
                _gg_side = "BUY"
            elif order.type == mt5.ORDER_TYPE_SELL_LIMIT:
                _gg_side = "SELL"
            if _gg_side and tf and _group_guard_is_blocked(tf, _gg_side, order.symbol):
                # เช็คก่อนว่า H/L เกิดแล้วหรือยัง → ถ้าเกิดแล้ว unblock แทน cancel
                _group_guard_check_unblock(tf, _gg_side, rates, order.symbol)
                if _group_guard_is_blocked(tf, _gg_side, order.symbol):
                    # H/L ยังไม่เกิด → ถ้าราคาเข้าใกล้ pending ให้ยกเลิก
                    _gg_sym = mt5.symbol_info(SYMBOL)
                    _gg_tick = mt5.symbol_info_tick(SYMBOL)
                    if _gg_sym and _gg_tick:
                        _gg_pt = _gg_sym.point or 0.01
                        _gg_near = config.SL_GUARD_NEAR_POINTS * _gg_pt * config.points_scale()
                        _gg_entry = order.price_open
                        _gg_cur = _gg_tick.ask if _gg_side == "BUY" else _gg_tick.bid
                        _gg_dist_pt = abs(_gg_cur - _gg_entry) / _gg_pt
                        if abs(_gg_cur - _gg_entry) <= _gg_near:
                            should_cancel = True
                            reason = (
                                f"SL Guard Group [{tf}]: {_gg_side} blocked, H/L ยังไม่เกิด — "
                                f"ยกเลิก pending entry:{_gg_entry:.2f} cur:{_gg_cur:.2f} "
                                f"dist:{_gg_dist_pt:.0f}pt (≤{config.SL_GUARD_NEAR_POINTS}pt)"
                            )

        if isinstance(info, dict) and not info.get("sl_armed") and info.get("intended_sl"):
            _is_s8 = info.get("sid") == 8
            _should_check_sl = _is_s8 or config.DELAY_SL_MODE != "off"
            if _should_check_sl:
                intended_sl = float(info.get("intended_sl", 0) or 0)
                sig = info.get("signal", "")
                arm_now = False
                arm_reason = ""

                if _is_s8 and config.DELAY_SL_MODE == "off":
                    # Original S8: wait for breakout beyond swing
                    swing_price = float(info.get("swing_price", 0) or 0)
                    swing_bar_time = int(info.get("swing_bar_time", 0) or 0)
                    latest_bar = rates[-1] if len(rates) > 0 else None
                    if swing_price > 0 and latest_bar is not None and int(latest_bar["time"]) > swing_bar_time:
                        if sig == "SELL" and float(latest_bar["high"]) > swing_price:
                            arm_now = True
                            arm_reason = "breakout above Swing High"
                        elif sig == "BUY" and float(latest_bar["low"]) < swing_price:
                            arm_now = True
                            arm_reason = "breakout below Swing Low"

                elif config.DELAY_SL_MODE == "time":
                    # Arm SL during the last 10% of the TF candle
                    import time as _time
                    _now_ts = int(_time.time())
                    _tf_secs = _get_tf_seconds(tf_val)
                    _threshold = _tf_secs * 0.10
                    _latest = rates[-1] if len(rates) > 0 else None
                    if _latest is not None:
                        _candle_end = int(_latest["time"]) + _tf_secs
                        _time_left = _candle_end - _now_ts
                        if _time_left <= _threshold:
                            arm_now = True
                            arm_reason = f"time left {_time_left}s < {_threshold:.0f}s (10% of {tf})"

                elif config.DELAY_SL_MODE == "price":
                    # BUY: ask > entry+spread / SELL: bid < entry-spread
                    _tick = mt5.symbol_info_tick(SYMBOL)
                    if _tick:
                        _entry_price = float(order.price_open)
                        _spread = abs(float(_tick.ask) - float(_tick.bid))
                        if sig == "BUY" and float(_tick.ask) > _entry_price + _spread:
                            arm_now = True
                            arm_reason = f"ask {float(_tick.ask):.2f} > entry+spread {_entry_price + _spread:.2f}"
                        elif sig == "SELL" and float(_tick.bid) < _entry_price - _spread:
                            arm_now = True
                            arm_reason = f"bid {float(_tick.bid):.2f} < entry-spread {_entry_price - _spread:.2f}"

                if arm_now:
                    ok_mod, r_mod = _modify_pending_sl(order, intended_sl)
                    if ok_mod:
                        info["sl_armed"] = True
                        info["sl_arm_retry_count"] = 0
                        pending_order_tf[ticket] = info
                        save_runtime_state()
                        sig_e = "🟢" if sig == "BUY" else "🔴"
                        ot = "BUY LIMIT" if sig == "BUY" else "SELL LIMIT"
                        await tg(app, (
                            f"🛡️ *ตั้ง SL {ot}*\n"
                            f"{sig_e} [{tf}] Ticket:`{ticket}`\n"
                            f"🛑 SL: `{intended_sl:.2f}`\n"
                            f"เหตุผล: {arm_reason}"
                        ))
                        print(f"🛡️ [{now}] arm SL {ot} {ticket}: SL={intended_sl:.2f} ({arm_reason})")
                    else:
                        info["sl_arm_retry_count"] = int(info.get("sl_arm_retry_count", 0) or 0) + 1
                        pending_order_tf[ticket] = info
                        save_runtime_state()
                        retcode = getattr(r_mod, "retcode", None) if r_mod is not None else None
                        comment = getattr(r_mod, "comment", "") if r_mod is not None else ""
                        print(
                            f"WARN [{now}] arm SL retry {ticket}: "
                            f"attempt={info['sl_arm_retry_count']} SL={intended_sl:.2f} "
                            f"retcode={retcode} comment={comment}"
                        )

        # Reverse limit: if 3 candles close after detect and still no fill -> cancel
        if isinstance(info, dict) and info.get("reverse"):
            detect_time = int(info.get("detect_bar_time", 0) or 0)
            if detect_time:
                bars_after_detect = [r for r in candle_rates if int(r["time"]) > detect_time]
                if len(bars_after_detect) >= 3:
                    should_cancel = True
                    reason = f"Reverse limit expired after 3 closed {check_tf} candles from the detect bar"

        # S8 Swing Limit: cancel when swing changes
        if not should_cancel and isinstance(info, dict) and info.get("swing_price") and info.get("sid") == 8:
            old_swing = info["swing_price"]
            sig = info.get("signal", "")
            if sig == "SELL":
                new_sh = _get_s6_prev_swing_high(rates, tf=tf)
                if new_sh and abs(new_sh["price"] - old_swing) > 0.01:
                    should_cancel = True
                    reason = f"Swing High changed {old_swing:.2f} -> {new_sh['price']:.2f}"
            elif sig == "BUY":
                new_sl = _get_s6_prev_swing_low(rates, tf=tf)
                if new_sl and abs(new_sl["price"] - old_swing) > 0.01:
                    should_cancel = True
                    reason = f"Swing Low changed {old_swing:.2f} -> {new_sl['price']:.2f}"

        # cancel_bars: cancel after N candles (e.g. Pattern E cancels after 1 candle)
        if not should_cancel and isinstance(info, dict) and info.get("cancel_bars"):
            detect_time = int(info.get("detect_bar_time", 0) or 0)
            if detect_time:
                bars_after = [r for r in candle_rates if int(r["time"]) > detect_time]
                if len(bars_after) >= info["cancel_bars"]:
                    should_cancel = True
                    reason = f"Expired after {info['cancel_bars']} candles ({check_tf})"

        if order.type == mt5.ORDER_TYPE_BUY_LIMIT:
            # BUY LIMIT: cancel when price closes above the main swing high
            if not should_cancel and last_close > swing_high:
                should_cancel = True
                reason = f"Close:{last_close:.2f} > Swing High:{swing_high:.2f}"
            # BUY LIMIT: next candle after detect closes red with body>=35% -> setup fails
            elif not should_cancel and config.CANCEL_NEXT_BAR_BODY_ENABLED:
                detect_time = info.get("detect_bar_time", 0) if isinstance(info, dict) else 0
                if detect_time:
                    next_bars = [r for r in candle_rates if int(r["time"]) > detect_time]
                    if next_bars:
                        nb = next_bars[0]
                        o_ = float(nb["open"]); c_ = float(nb["close"])
                        rng = float(nb["high"]) - float(nb["low"])
                        body = abs(c_-o_)/rng if rng > 0 else 0
                        if c_ < o_ and body >= 0.35:
                            should_cancel = True
                            reason = (f"Next {check_tf} candle closes red body:{body*100:.0f}%"
                                      f" O:{o_:.2f} H:{float(nb['high']):.2f}"
                                      f" L:{float(nb['low']):.2f} C:{c_:.2f}"
                                      f" setup failed")

        elif order.type == mt5.ORDER_TYPE_SELL_LIMIT:
            # SELL LIMIT: ลบเมื่อราคาปิดต่ำกว่า Swing Low หลัก
            if not should_cancel and last_close < swing_low:
                should_cancel = True
                reason = f"Close:{last_close:.2f} < Swing Low:{swing_low:.2f}"
            # SELL LIMIT: แท่งถัดจาก detect ปิดเขียว body>=35% -> setup ล้มเหลว
            elif not should_cancel and config.CANCEL_NEXT_BAR_BODY_ENABLED:
                detect_time = info.get("detect_bar_time", 0) if isinstance(info, dict) else 0
                if detect_time:
                    next_bars = [r for r in candle_rates if int(r["time"]) > detect_time]
                    if next_bars:
                        nb = next_bars[0]
                        o_ = float(nb["open"]); c_ = float(nb["close"])
                        rng = float(nb["high"]) - float(nb["low"])
                        body = abs(c_-o_)/rng if rng > 0 else 0
                        if c_ > o_ and body >= 0.35:
                            should_cancel = True
                            reason = (f"แท่งถัดไป{check_tf}เขียว body:{body*100:.0f}%"
                                      f" O:{o_:.2f} H:{float(nb['high']):.2f}"
                                      f" L:{float(nb['low']):.2f} C:{c_:.2f}"
                                      f" setup ล้มเหลว")

        # Premium/Discount zone recheck
        if not should_cancel and isinstance(info, dict) and _order_sid not in set(getattr(config, "PDFIBOPLUS_SKIP_SIDS", ())):
            _is_combined = _triple_check_all_enabled()
            pd_status, pd_msgs = _pdfiboplus_process(ticket, order, info, combined=_is_combined)
            for _msg in pd_msgs:
                await tg(app, _msg)
            if _is_combined:
                # แบบรวม: ครบ 2 รอบ (pd_status != "wait") → นับเป็น 1 โหวต
                if pd_status != "wait":
                    _triple_check_record(
                        ticket, "pd", pd_status == "pass",
                        tf=tf,
                        signal=info.get("signal", "") if isinstance(info, dict) else "",
                    )
            else:
                # แบบแยก: fail (รอบ 1 หรือ รอบ 2) → ยกเลิก order ทันที
                if pd_status == "fail":
                    should_cancel = True
                    reason = "PD Zone Recheck: order อยู่นอก Premium/Discount zone"
                    _pdfiboplus_state.pop(ticket, None)

        # Combined Triple Recheck decision (เมื่อเปิดครบทั้ง 3 อัน)
        if not should_cancel and _triple_check_all_enabled():
            tc_dec = _triple_check_evaluate(ticket)
            if tc_dec in ("cancel", "keep"):
                tc_st    = _triple_check_state.pop(ticket, {})
                _tc_sig  = _pending_order_icon(order)
                _tc_ot   = _pending_order_type_name(order)
                _tc_line = (
                    f"RSI {_triple_r(tc_st.get('rsi'))} | "
                    f"Trend {_triple_r(tc_st.get('trend'))} | "
                    f"PD {_triple_r(tc_st.get('pd'))}"
                )
                log_event(
                    "TRIPLE_RECHECK",
                    tc_dec.upper(),
                    ticket=ticket, tf=tf,
                    rsi=tc_st.get("rsi"), trend=tc_st.get("trend"), pd=tc_st.get("pd"),
                )
                if tc_dec == "cancel":
                    should_cancel = True
                    reason = f"Triple Recheck < 2/3: {_tc_line}"
                else:
                    await tg(app, (
                        f"✅ *Triple Recheck ผ่าน 2/3 — Keep Order*\n"
                        f"{_tc_sig} {_tc_ot} [{tf}] `#{ticket}`\n"
                        f"{_tc_line}"
                    ))

        if should_cancel:
            r = mt5.order_send({
                "action": mt5.TRADE_ACTION_REMOVE,
                "order":  ticket,
            })
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                pending_order_tf.pop(ticket, None)
                sig_e = _pending_order_icon(order)
                ot    = _pending_order_type_name(order)
                log_event(
                    "ORDER_CANCELED",
                    reason,
                    ticket=ticket,
                    tf=tf,
                    side=_pending_order_side(order),
                    order_type=ot,
                    entry=order.price_open,
                    flow_id=info.get("flow_id", "") if isinstance(info, dict) else "",
                    parent_flow_id=info.get("parent_flow_id", "") if isinstance(info, dict) else "",
                )
                await tg(app, (
                        f"🗑️ *ยกเลิก {ot} อัตโนมัติ*\n"
                        f"{sig_e} [{tf}] Ticket:`{ticket}`\n"
                        f"Entry:`{order.price_open}`\n"
                        f"Flow: `{_short_flow_id(info.get('flow_id', ''))}`\n"
                        f"เหตุผล: {reason}"
                    ))
                print(f"🗑️ [{now}] ยกเลิก {ot} {ticket} [{tf}]: {reason}")
            else:
                # order_send ไม่สำเร็จ (ticket อาจ fill/ถูกลบไปแล้วพอดี หรือ MT5 busy ชั่วคราว)
                # เดิมไม่ log อะไรเลย → ตามรอยไม่ได้ว่า "ทำไม order หาย" (รอบถัดไปอาจ retry สำเร็จแล้ว log ปกติ)
                log_event(
                    "ORDER_CANCEL_FAILED",
                    reason,
                    ticket=ticket,
                    tf=tf,
                    retcode=(r.retcode if r else None),
                    comment=(getattr(r, "comment", "") if r else ""),
                )


# -------------------------------------------------------------
async def check_limit_sweep(app):
    """
    Limit Sweep - เมื่อ position จบแท่งสวนทาง + ราคาทะลุ prev low/high
    BUY:  แท่งจบแดง + close < prev low -> ปิด position + sweep BUY LIMITs ใน TF
          -> เหลือตัวใกล้ Swing LL ที่สุด / ถ้าไม่มี -> ตั้ง S8 ที่ LL
    SELL: แท่งจบเขียว + close > prev high -> ปิด position + sweep SELL LIMITs ใน TF
          -> เหลือตัวใกล้ Swing HH ที่สุด / ถ้าไม่มี -> ตั้ง S8 ที่ HH
    """
    if not config.LIMIT_SWEEP:
        return

    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        _sweep_last_bar.clear()
        return

    now = now_bkk().strftime("%H:%M:%S")
    open_tickets = {p.ticket for p in positions}
    # cleanup stale tickets
    for t in list(_sweep_last_bar.keys()):
        if t not in open_tickets:
            _sweep_last_bar.pop(t, None)

    for pos in positions:
        ticket = pos.ticket
        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        tf = position_tf.get(ticket)
        if not tf:
            continue

        # ดึง rates
        tf_val = TF_OPTIONS.get(tf, mt5.TIMEFRAME_M1)
        lookback = TF_LOOKBACK.get(tf, SWING_LOOKBACK)
        rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, lookback + 6)
        if rates is None or len(rates) < 6:
            continue

        # แท่งปิดล่าสุด = rates[-2], แท่งก่อนหน้า = rates[-3]
        bar = rates[-2]
        prev_bar = rates[-3]
        bar_time = int(bar["time"])

        # ไม่ตรวจแท่งเดิมซ้ำ
        if _sweep_last_bar.get(ticket) == bar_time:
            continue

        bar_close = float(bar["close"])
        bar_open = float(bar["open"])
        prev_low = float(prev_bar["low"])
        prev_high = float(prev_bar["high"])

        is_red = bar_close < bar_open
        is_green = bar_close > bar_open

        trigger = False
        if pos_type == "BUY" and is_red and bar_close < prev_low:
            trigger = True
        elif pos_type == "SELL" and is_green and bar_close > prev_high:
            trigger = True

        _sweep_last_bar[ticket] = bar_time

        if not trigger:
            continue

        entry = float(pos.price_open)
        sig = "BUY" if pos_type == "BUY" else "SELL"
        opp = "SELL" if pos_type == "BUY" else "BUY"

        # -- 1) ปิด position --
        comment = f"Sweep_{tf}"
        ok, close_price = _close_position(pos, pos_type, comment)
        if not ok:
            print(f"[{now}] ⚠️ Limit Sweep: ปิด {pos_type} #{ticket} ไม่สำเร็จ")
            continue

        reason_detail = (f"แท่งจบ{'แดง' if is_red else 'เขียว'} close={bar_close:.2f} "
                         f"{'< prev low' if pos_type == 'BUY' else '> prev high'}="
                         f"{prev_low if pos_type == 'BUY' else prev_high:.2f}")
        print(f"[{now}] 🧹 Limit Sweep: ปิด {pos_type} #{ticket} [{tf}] {reason_detail}")

        # -- 2) หา Swing LL (BUY) หรือ HH (SELL) --
        sh_info = _get_s6_prev_swing_high(rates, tf=tf)
        sl_info = _get_s6_prev_swing_low(rates, tf=tf)

        if pos_type == "BUY":
            target_info = _find_ll(rates, sl_info)  # LL = swing low ที่ต่ำกว่า L
            while target_info and bar_close <= float(target_info["price"]):
                target_info = _find_ll(rates, target_info)
            target_price = target_info["price"] if target_info else None
            limit_type = mt5.ORDER_TYPE_BUY_LIMIT
        else:
            target_info = _find_hh(rates, sh_info)  # HH = swing high ที่สูงกว่า H
            while target_info and bar_close >= float(target_info["price"]):
                target_info = _find_hh(rates, target_info)
            target_price = target_info["price"] if target_info else None
            limit_type = mt5.ORDER_TYPE_SELL_LIMIT

        # -- 3) หา limit orders ใน TF เดียวกัน --
        #   ในช่วง LL-H / L-HH -> ยกเลิกทุกท่า
        #   นอกช่วง -> ยกเลิกเฉพาะท่าที่ 8
        h_price = sh_info["price"] if sh_info else None
        l_price = sl_info["price"] if sl_info else None
        orders = mt5.orders_get(symbol=SYMBOL)
        in_range_limits = []
        if orders:
            for o in orders:
                o_info = pending_order_tf.get(o.ticket)
                o_tf = o_info.get("tf") if isinstance(o_info, dict) else o_info
                if o_tf != tf:
                    continue
                o_sid = o_info.get("sid") if isinstance(o_info, dict) else None
                ep = o.price_open
                if pos_type == "BUY" and o.type == mt5.ORDER_TYPE_BUY_LIMIT:
                    in_rng = target_price and h_price and target_price <= ep <= h_price
                    if in_rng or o_sid == 8:
                        in_range_limits.append(o)
                elif pos_type == "SELL" and o.type == mt5.ORDER_TYPE_SELL_LIMIT:
                    in_rng = target_price and l_price and l_price <= ep <= target_price
                    if in_rng or o_sid == 8:
                        in_range_limits.append(o)

        # -- 4) เหลือตัวใกล้ LL/HH ที่สุด ยกเลิกตัวที่เหลือในช่วง --
        kept_ticket = None
        if target_price and in_range_limits:
            in_range_limits.sort(key=lambda o: abs(o.price_open - target_price))
            kept_ticket = in_range_limits[0].ticket
            for o in in_range_limits[1:]:
                r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                ok_cancel = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
                status = "✅" if ok_cancel else "❌"
                print(f"[{now}] 🧹 Sweep cancel {pos_type} LIMIT #{o.ticket} [{tf}] entry={o.price_open:.2f} {status}")
                pending_order_tf.pop(o.ticket, None)
            rng = f"{'LL' if pos_type == 'BUY' else 'L'}-{'H' if pos_type == 'BUY' else 'HH'}"
            print(f"[{now}] 🧹 Sweep keep #{kept_ticket} [{tf}] ใกล้ {'LL' if pos_type == 'BUY' else 'HH'}={target_price:.2f} (range {rng})")

        # -- 5) ถ้าไม่มี limit ใกล้ target -> ตั้ง S8 --
        if target_info and not kept_ticket:
            candle = target_info.get("candle", {})
            c_high = candle.get("high", 0)
            c_low = candle.get("low", 0)
            c_range = c_high - c_low

            if c_range > 0:
                from mt5_utils import open_order
                if pos_type == "BUY":
                    s8_entry = round(c_low - c_range * 0.17, 2)
                    s8_sl = round(c_low - c_range * 0.31, 2)
                    s8_tp = sh_info["price"] if sh_info else round(c_high, 2)
                    s8_signal = "BUY"
                else:
                    s8_entry = round(c_high + c_range * 0.17, 2)
                    s8_sl = round(c_high + c_range * 0.31, 2)
                    s8_tp = sl_info["price"] if sl_info else round(c_low, 2)
                    s8_signal = "SELL"

                s8_pattern = f"ท่าที่ 8 กินไส้ Swing [Limit Sweep] {'🟢 BUY' if s8_signal == 'BUY' else '🔴 SELL'}"
                vol = config.get_volume()
                res = open_order(s8_signal, vol, s8_sl, s8_tp,
                                 entry_price=s8_entry, tf=tf, sid="8", pattern=s8_pattern)
                if res.get("success"):
                    s8_ticket = res["ticket"]
                    pending_order_tf[s8_ticket] = {
                        "tf": tf, "signal": s8_signal,
                        "detect_bar_time": bar_time,
                        "sid": 8, "pattern": s8_pattern,
                        "source": "limit_sweep",
                        "swing_price": target_price,
                        "swing_bar_time": int(target_info.get("time", 0)),
                    }
                    position_pattern[s8_ticket] = s8_pattern
                    log_event(
                        "ORDER_CREATED",
                        s8_pattern,
                        tf=tf,
                        sid=8,
                        signal=s8_signal,
                        entry=s8_entry,
                        sl=s8_sl,
                        tp=s8_tp,
                        ticket=s8_ticket,
                        order_type=res.get("order_type", "LIMIT"),
                        source="limit_sweep",
                        from_ticket=ticket,
                    )
                    print(f"[{now}] 🧹 Sweep -> S8 {s8_signal} LIMIT #{s8_ticket} [{tf}] "
                          f"Entry={s8_entry:.2f} SL={s8_sl:.2f} TP={s8_tp:.2f} "
                          f"{'LL' if pos_type == 'BUY' else 'HH'}={target_price:.2f}")
                    await tg(app,
                        f"🧹 *Limit Sweep -> S8*\n"
                        f"━━━━━━━━━━━━━━━━━\n"
                        f"ปิด {pos_type} `#{ticket}` [{tf}]\n"
                        f"{reason_detail}\n\n"
                        f"ตั้ง {s8_signal} LIMIT `#{s8_ticket}`\n"
                        f"📌 Entry: `{s8_entry:.2f}`\n"
                        f"🛑 SL: `{s8_sl:.2f}` | 🎯 TP: `{s8_tp:.2f}`\n"
                        f"{'📉 LL' if pos_type == 'BUY' else '📈 HH'}: `{target_price:.2f}`"
                    )
                else:
                    err = res.get("error", "?")
                    print(f"[{now}] ⚠️ Sweep S8 failed: {err}")
                    await tg(app,
                        f"🧹 *Limit Sweep*\n"
                        f"ปิด {pos_type} `#{ticket}` [{tf}]\n"
                        f"{reason_detail}\n\n"
                        f"⚠️ S8 {'LL' if pos_type == 'BUY' else 'HH'} ตั้งไม่สำเร็จ: {err}"
                    )
            else:
                await tg(app,
                    f"🧹 *Limit Sweep*\n"
                    f"ปิด {pos_type} `#{ticket}` [{tf}]\n"
                    f"{reason_detail}\n\n"
                    f"{'📉 LL' if pos_type == 'BUY' else '📈 HH'}: `{target_price:.2f}` (range=0 ข้าม S8)"
                )
        else:
            sweep_msg = ""
            if kept_ticket:
                sweep_msg = f"\nเหลือ LIMIT `#{kept_ticket}` ใกล้ {'LL' if pos_type == 'BUY' else 'HH'}"
            elif target_price:
                sweep_msg = f"\nไม่มี LIMIT ใน TF"
            await tg(app,
                f"🧹 *Limit Sweep*\n"
                f"ปิด {pos_type} `#{ticket}` [{tf}]\n"
                f"{reason_detail}{sweep_msg}"
            )

        # cleanup state
        _entry_state.pop(ticket, None)
        _trail_state.pop(ticket, None)
        _bar_count.pop(ticket, None)
        position_tf.pop(ticket, None)
        position_sid.pop(ticket, None)
        position_pattern.pop(ticket, None)
        position_trend_filter.pop(ticket, None)
        _s6_state.pop(ticket, None)
        _s6i_state.pop(ticket, None)
        _sweep_last_bar.pop(ticket, None)
        _trend_recheck_state.pop(ticket, None)
        _fill_trend_checked.discard(ticket)
        config.save_runtime_state()


async def check_fvg_candle_quality(app):
    """Deprecated - ท่าที่ 2 ใช้ check_entry_candle_quality เหมือนทุกท่าแล้ว"""
    pass


# -------------------------------------------------------------
async def _s12_close_all(app, reason: str):
    """ปิด S12 positions ทั้งหมด - ใช้ใน flip + breakout"""
    from strategy12 import _s12_state
    from bot_log import log_event

    positions   = mt5.positions_get(symbol=SYMBOL)
    s12_tickets = set(_s12_state["tickets"])
    closed = 0
    total_profit = 0.0

    if positions:
        tick = mt5.symbol_info_tick(SYMBOL)
        for pos in positions:
            if pos.ticket not in s12_tickets:
                continue
            close_type  = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            close_price = float(tick.bid) if pos.type == mt5.ORDER_TYPE_BUY else float(tick.ask)
            r = mt5.order_send({
                "action":       mt5.TRADE_ACTION_DEAL,
                "symbol":       SYMBOL,
                "volume":       pos.volume,
                "type":         close_type,
                "position":     pos.ticket,
                "price":        close_price,
                "deviation":    20,
                "magic":        0,
                "comment":      "S12 close",
                "type_time":    mt5.ORDER_TIME_GTC,
                "type_filling": _get_filling_mode(),
            })
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                closed += 1
                total_profit += pos.profit
                log_event("POSITION_CLOSED", reason,
                          ticket=pos.ticket,
                          side="BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL",
                          symbol=SYMBOL, tf="M5", sid=12,
                          open_price=pos.price_open, close_price=close_price,
                          profit=round(pos.profit, 2))

    _s12_state["tickets"].clear()
    _s12_state["order_count"] = 0
    _s12_state["last_entry_price"] = None
    # side ไม่ล้างที่นี่ - caller กำหนดเอง

    now_str = now_bkk().strftime("%H:%M:%S")
    profit_str = f"+{total_profit:.2f}" if total_profit >= 0 else f"{total_profit:.2f}"
    print(f"🗑️ [{now_str}] S12 ปิด {closed} positions profit={profit_str}: {reason}")
    await tg(app, (
        f"🗑️ *S12 ปิด {closed} position*\n"
        f"Profit: `{profit_str}`\n"
        f"เหตุผล: {reason}"
    ))


async def check_s12_management(app):
    """S12 Range Trading management - ตรวจ flip + breakout"""
    from strategy12 import _s12_state, s12_get_swing_context, s12_cleanup_tickets

    if not active_strategies.get(12, False):
        return

    s12_cleanup_tickets()

    if not _s12_state["tickets"]:
        return

    rates_m5 = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, config.S12_LOOKBACK + 5)
    tick     = mt5.symbol_info_tick(SYMBOL)
    sym      = mt5.symbol_info(SYMBOL)

    if rates_m5 is None or len(rates_m5) < 5 or tick is None or sym is None:
        return

    pt        = sym.point or 0.01
    scale     = config.points_scale()
    zone_dist = config.S12_ZONE_POINTS * pt * scale
    side      = _s12_state["side"]

    context = s12_get_swing_context(rates_m5, config.S12_LOOKBACK)
    if not context:
        return
    swing_high = context["pivot_swing_high"]
    swing_low = context["pivot_swing_low"]

    # -- ตรวจ Breakout (แท่งปิดล่าสุด) --
    if len(rates_m5) >= 2:
        last_close = float(rates_m5[-2]["close"])
        if side == "BUY" and last_close > swing_high:
            await _s12_close_all(app, f"Breakout ขึ้น close:{last_close:.2f} > {swing_high:.2f}")
            _s12_state["side"] = None
            return
        elif side == "SELL" and last_close < swing_low:
            await _s12_close_all(app, f"Breakout ลง close:{last_close:.2f} < {swing_low:.2f}")
            _s12_state["side"] = None
            return

    # -- ตรวจ Flip --
    bid = float(tick.bid)
    ask = float(tick.ask)

    if side == "SELL" and ask <= swing_low + zone_dist:
        await _s12_close_all(app, f"Flip -> BUY: ราคาถึง bottom zone {swing_low:.2f}")
        _s12_state["side"]             = "BUY"
        _s12_state["order_count"]      = 0
        _s12_state["last_entry_price"] = None
    elif side == "BUY" and bid >= swing_high - zone_dist:
        await _s12_close_all(app, f"Flip -> SELL: ราคาถึง top zone {swing_high:.2f}")
        _s12_state["side"]             = "SELL"
        _s12_state["order_count"]      = 0
        _s12_state["last_entry_price"] = None


_s14_engulf_exit_checked = set()

async def check_s14_engulf_exits(app):
    """
    S14 Engulf exit rule:
    ถ้าแท่ง หลังแท่ง sweep (HTF bar หลัง entry) จบตามทิศทาง (GREEN สำหรับ SELL, RED สำหรับ BUY) ให้ปิด position ทันที
    """
    if not active_strategies.get(14, False):
        return

    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        return

    from strategy14 import _get_s14_htf, TF_SECONDS
    
    for pos in positions:
        ticket = int(pos.ticket)
        # Check if the position belongs to S14 engulf or sweep
        sid = position_sid.get(ticket)
        pattern = position_pattern.get(ticket) or ""
        
        # If not tracked in memory, try parsing comment
        comment = getattr(pos, "comment", "")
        if sid is None:
            if "_S14_" in comment:
                sid = 14
        
        is_engulf = False
        is_sweep = False
        if sid == 14:
            # BES/SES = new engulf codes, BSS/SSS = old engulf codes (backward compat)
            is_engulf = any(x in comment.upper() for x in ["BES", "SES", "BSS", "SSS"]) or "engulf swing" in pattern.lower() or "sweep swing" in pattern.lower()
            is_sweep  = any(x in comment.upper() for x in ["BRS", "SRS"]) or "sweep กลับตัว" in pattern.lower()
        
        if sid != 14 or (not is_engulf and not is_sweep):
            continue
            
        # ── Check Secondary HTF exit logic first (only for engulf) ──
        zone_meta = position_zone_meta.get(ticket) or {}
        sec_htf = zone_meta.get("sec_htf")
        ref_level = zone_meta.get("s14_ref_level")
        entry_time = int(pos.time)
        
        if is_engulf and sec_htf and ref_level is not None:
            sec_htf_secs = TF_SECONDS.get(sec_htf, 1800)
            sec_htf_start = (entry_time // sec_htf_secs) * sec_htf_secs
            sec_htf_end = sec_htf_start + sec_htf_secs
            
            tick = mt5.symbol_info_tick(SYMBOL)
            if tick:
                curr_time = int(tick.time)
                if curr_time >= sec_htf_end:
                    sec_htf_const = getattr(mt5, f"TIMEFRAME_{sec_htf.upper()}")
                    sec_rates = mt5.copy_rates_range(SYMBOL, sec_htf_const, sec_htf_start, sec_htf_start + 10)
                    sec_bar = None
                    if sec_rates is not None and len(sec_rates) > 0:
                        for r in sec_rates:
                            if int(r["time"]) == sec_htf_start:
                                sec_bar = r
                                break
                    if sec_bar is not None:
                        sec_c = float(sec_bar["close"])
                        is_buy = pos.type == mt5.ORDER_TYPE_BUY
                        should_close = False
                        if is_buy:
                            if sec_c < ref_level:
                                should_close = True
                        else:
                            if sec_c > ref_level:
                                should_close = True
                                
                        if should_close:
                            if getattr(config, "S14_ENGULF_BREAKEVEN", True):
                                new_tp = round(float(pos.price_open), 2)
                                ok = _modify_sl_tp(pos, pos.sl, new_tp)
                                if ok:
                                    log_event("S14_SEC_HTF_BREAKEVEN", f"TP=entry set for S14 position, {sec_htf} closed {'below' if is_buy else 'above'} ref {ref_level:.2f} (close={sec_c:.2f})", ticket=ticket)
                                    await tg(app, f"⚠️ *S14 Engulf ย้าย TP = Entry*\nTicket: `{ticket}` | HTF: `{sec_htf}`\nแท่ง {sec_htf} ปิด `{sec_c:.2f}` {'ต่ำกว่า' if is_buy else 'สูงกว่า'} ref `{ref_level:.2f}`\n→ TP ใหม่ = `{new_tp:.2f}` (entry)")
                                    position_zone_meta.pop(ticket, None)
                                else:
                                    retry = zone_meta.get("breakeven_retry", 0) + 1
                                    if retry >= 3:
                                        log_event("S14_SEC_HTF_BREAKEVEN_FAIL", f"Failed to set TP=entry after {retry} retries, giving up", ticket=ticket)
                                        position_zone_meta.pop(ticket, None)
                                    else:
                                        zone_meta["breakeven_retry"] = retry
                                        position_zone_meta[ticket] = zone_meta
                            else:
                                position_zone_meta.pop(ticket, None)
                            continue
                        else:
                            # ปิดแท่งแบบไม่ใช่ engulf (ปลอดภัย) -> เคลียร์ meta เพื่อไม่ต้องเช็คซ้ำ
                            position_zone_meta.pop(ticket, None)
                            save_runtime_state()
            
        if ticket in _s14_engulf_exit_checked:
            continue
            
        # Determine TF
        tf = position_tf.get(ticket)
        if not tf:
            comment = getattr(pos, "comment", "")
            parts = comment.split("_")
            if parts:
                tf = parts[0]
            else:
                tf = "M1"
                
        # Get Check TF and check_secs
        if is_sweep:
            check_tf = tf
            check_secs = TF_SECONDS.get(check_tf, 60)
            # ── Case A vs Case B ──────────────────────────────────────────────
            # Case A: sweep bar เขียว (BUY) / แดง (SELL) → เข้าทันที
            #   exit bar = แท่งถัดจาก sweep bar (ไม่ใช่แท่งที่ entry อยู่)
            # Case B: รอ confirm bar → exit bar = แท่งที่ entry/confirm bar อยู่
            #
            # ใช้ s14_sweep_bar_time จาก zone_meta เพื่อแยก Case A ออกจาก Case B
            # (เก็บไว้ใน scanner.py ตอน place order สำหรับ sweep pattern)
            _sweep_bar_t = zone_meta.get("s14_sweep_bar_time")
            if _sweep_bar_t:
                # Case A: entry time ≈ sweep bar time → exit bar = sweep bar + 1 bar
                sweep_bar_start = (_sweep_bar_t // check_secs) * check_secs
                exit_bar_start = sweep_bar_start + check_secs
            else:
                # Case B: เดิม — exit bar = แท่งที่ entry อยู่ (confirm bar)
                exit_bar_start = (entry_time // check_secs) * check_secs
            exit_bar_end = exit_bar_start + check_secs

        else: # is_engulf
            htf = _get_s14_htf(tf)
            check_tf = htf
            check_secs = TF_SECONDS.get(check_tf, 300)
            entry_htf_start = (entry_time // check_secs) * check_secs
            exit_bar_start = entry_htf_start
            exit_bar_end = exit_bar_start + check_secs
        
        # Get current time (server time)
        tick = mt5.symbol_info_tick(SYMBOL)
        if not tick:
            continue
        curr_time = int(tick.time)
        
        # If the exit bar has not closed yet, wait
        if curr_time < exit_bar_end:
            continue
            
        # Exit bar has closed! Fetch the completed exit bar
        check_tf_const = getattr(mt5, f"TIMEFRAME_{check_tf.upper()}")
        rates_raw = mt5.copy_rates_from_pos(SYMBOL, check_tf_const, 0, 5)
        if rates_raw is None or len(rates_raw) == 0:
            continue
            
        # Find the bar starting at exit_bar_start
        exit_bar = None
        for r in rates_raw:
            if int(r["time"]) == exit_bar_start:
                exit_bar = r
                break
                
        if exit_bar is None:
            rates_range = mt5.copy_rates_range(SYMBOL, check_tf_const, exit_bar_start, exit_bar_start + 10)
            if rates_range is not None and len(rates_range) > 0:
                exit_bar = rates_range[0]
                
        if exit_bar is None:
            continue
            
        # Mark as checked
        _s14_engulf_exit_checked.add(ticket)
        
        # Check color of exit bar
        o = float(exit_bar["open"])
        c = float(exit_bar["close"])
        is_buy = pos.type == mt5.ORDER_TYPE_BUY
        
        should_close = False
        if is_buy: # BUY position (sweep_low)
            if c < o: # closed RED
                should_close = True
        else: # SELL position (sweep_high)
            if c > o: # closed GREEN
                should_close = True
                
        if should_close:
            pos_type = "BUY" if is_buy else "SELL"
            ok, cp = _close_position(pos, pos_type, f"S14 {'sweep' if is_sweep else 'engulf'} exit color rule ({check_tf})")
            if ok:
                log_event("S14_EXIT", f"Closed S14 {'sweep' if is_sweep else 'engulf'} position due to {check_tf} exit bar color rule", ticket=ticket)
                await tg(app, f"⚡ *S14 {'Sweep' if is_sweep else 'Engulf'} ปิดตำแหน่งทันที*\nTicket: `{ticket}`\nเหตุผล: แท่งถัดจาก sweep ({check_tf}) จบ{'แดง' if is_buy else 'เขียว'} ขัดทิศทาง")
