from config import *
import config
import re
import inspect
import os
from bot_log import LOG_DIR, log_event
from mt5_utils import connect_mt5
from strategy4 import _find_prev_swing_high, _find_prev_swing_low, _find_hh, _find_ll

# ── FVG order quality tracking ──────────────────────────────
fvg_order_tickets: dict = {}

# ── mapping: ticket → {tf, gap_bot, gap_top} สำหรับ limit orders ─
pending_order_tf: dict = {}   # {ticket: {tf, gap_bot, gap_top}}

# ── mapping: position ticket → tf_name (ทุกท่า) ────────────
position_tf: dict = {}   # {ticket: tf_name}

# ── mapping: position ticket → strategy id ──────────────────
position_sid: dict = {}  # {ticket: 2|3}

# ── mapping: position ticket → pattern name ─────────────────
position_pattern: dict = {}  # {ticket: "pattern string"}
position_trend_filter: dict = {}  # {ticket: "bull_strong,sideway"}

# ── Trail SL state per ticket ────────────────────────────────
_trail_state: dict = {}
_trend_filter_last_dir: dict = {}  # {"ticket|tf": "BULL"|"BEAR"|"SIDEWAY"}

# ── ข้อ 4: นับแท่งหลัง order เข้า ─────────────────────────
_bar_count: dict = {}

# ── ข้อ 5: สถานะตรวจ entry candle ──────────────────────────
_entry_state: dict = {}   # {ticket: "done" | "waiting_next"}

# ── Fill notification tracking ──────────────────────────────
_fill_notified: dict = {}        # {ticket: True} ถ้าแจ้ง fill แล้ว
_entry_bar_notified: dict = {}   # {ticket: True} ถ้าแจ้งแท่ง entry แล้ว
_fill_initialized: bool = False  # True หลังจาก pre-populate _fill_notified ครั้งแรก
_entry_bar_none_first: dict = {} # {ticket: monotonic_time} ครั้งแรกที่ entry_bar=None
_reverse_tickets: set = set()    # ticket ที่เปิดจาก reverse (entry candle สวนทาง)
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
_s8_fill_sl: dict = {}   # {ticket: intended_sl} สำหรับ S8 ที่ fill ก่อน arm SL

# ── Strategy 6: 2 High 2 Low trail state ────────────────────
# {ticket: {
#   "swing_h": float,        ← Swing High ที่รอสัมผัส
#   "phase": "wait"|"count", ← wait=รอสัมผัส, count=นับ 1-5
#   "count": int,
#   "last_bar_time": int,
#   "trail_count": int,      ← จำนวนรอบที่ trail แล้ว
# }}
_s6_state: dict = {}

# ── Strategy 6 Independent: trail ทุก position (ไม่จำกัดท่า 2/3) ─
_s6i_state: dict = {}

# ── Limit Sweep: track แท่งที่ตรวจแล้ว per ticket ────────────
_sweep_last_bar: dict = {}  # {ticket: last_checked_bar_time}

# ── Focus Opposite: frozen_side marker แยกต่อฟีเจอร์ ────────
# "trail_sl"     → ใช้โดย check_engulf_trail_sl / SL ปกป้อง
# "entry_candle" → ใช้โดย check_entry_candle_quality
# ค่า: "BUY" | "SELL" | None
_focus_frozen_side: dict = {"trail_sl": None, "entry_candle": None}


def _parse_bot_comment(comment: str):
    """Parse comment เช่น M1_S2, H4_S3, M1_S6i_buy → (tf, sid)"""
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
    """หา tf/sid ของ position จาก comment ของ position หรือ entry deal history"""
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


# ─────────────────────────────────────────────────────────────
def _get_filling_mode():
    """คืน fill type ที่ broker รองรับ (IOC → FOK → RETURN)"""
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
        f"SL: `{old_sl:.2f}` → `{new_sl:.2f}`\n"
        f"TP: `{old_tp:.2f}` → `{new_tp:.2f}`"
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
            f"SL: `{old_sl:.2f}` → `{new_sl:.2f}`\n"
            f"TP: `{old_tp:.2f}` → `{new_tp:.2f}`\n"
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
        f"SL: `{old_sl:.2f}` → `{new_sl:.2f}`\n"
        f"TP: `{old_tp:.2f}` → `{new_tp:.2f}`"
    ))
    _last_sltp_tg_key = key


def _close_position(pos, pos_type, comment):
    """ปิด position ทันที คืน (success, close_price)"""
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
    success = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
    if success:
        print(f"[{now_bkk().strftime('%H:%M:%S')}] CLOSE_DEBUG ok {pos_type} ticket={pos.ticket} close={close_price:.2f} bid={bid:.2f} ask={ask:.2f} spread={spread:.2f} entry={float(pos.price_open):.2f} reason=[{comment}]")
        print(f"[{now_bkk().strftime('%H:%M:%S')}] 🔴 _close_position: {pos_type} ticket={pos.ticket} price={close_price:.2f} reason=[{comment}]")
        log_event("POSITION_CLOSE_REQUEST", comment, ticket=pos.ticket, side=pos_type, close_price=close_price, entry=pos.price_open, bid=bid, ask=ask, spread=spread, ok=True)
    else:
        retcode = r.retcode if r is not None else "None"
        print(f"[{now_bkk().strftime('%H:%M:%S')}] CLOSE_DEBUG fail {pos_type} ticket={pos.ticket} bid={bid:.2f} ask={ask:.2f} spread={spread:.2f} entry={float(pos.price_open):.2f} retcode={retcode} reason=[{comment}]")
        print(f"[{now_bkk().strftime('%H:%M:%S')}] ❌ _close_position FAIL: {pos_type} ticket={pos.ticket} retcode={retcode} reason=[{comment}]")
        log_event("POSITION_CLOSE_REQUEST", comment, ticket=pos.ticket, side=pos_type, entry=pos.price_open, bid=bid, ask=ask, spread=spread, ok=False, retcode=retcode)
    return success, close_price


def _get_sltp_caller():
    """หาว่าใครเป็นคนเรียกแก้ SL/TP จริง"""
    skip = {"_modify_sl", "_modify_sl_tp", "_apply_entry_sl_tp", "_get_sltp_caller", "_log_sltp_change"}
    for frame in inspect.stack()[1:]:
        if frame.function not in skip:
            return f"{frame.function}:{frame.lineno}"
    return "unknown"


def _trade_debug_enabled() -> bool:
    return bool(getattr(config, "TRADE_DEBUG", False))


def _log_sltp_change(mode, caller, pos, new_sl, new_tp, ok, result):
    """log forensic สำหรับตามรอยว่าใครเป็นคนเปลี่ยน SL/TP"""
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
    """แก้ SL ของ position"""
    r = mt5.order_send({
        "action":   mt5.TRADE_ACTION_SLTP,
        "symbol":   SYMBOL,
        "position": pos.ticket,
        "sl":       new_sl,
        "tp":       pos.tp,
    })
    ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
    _log_sltp_change("SL_ONLY", caller, pos, new_sl, pos.tp, ok, r)
    return ok


def _modify_sl_tp(pos, new_sl, new_tp):
    caller = _get_sltp_caller()
    """แก้ SL และ TP ของ position พร้อมกัน"""
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
    """แก้ SL ของ pending order"""
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


def _apply_entry_sl_tp(pos, new_sl, new_tp):
    """ปรับ SL/TP ตาม flag: default ปรับเฉพาะ SL ไม่แตะ TP"""
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
    ดึงแท่งที่ถูกต้องตาม state:
    - คืน (entry_bar, next_bar)
    - entry_bar = แท่งที่ราคา fill จริง
    - next_bar  = แท่งถัดจาก entry_bar (ปิดสมบูรณ์แล้ว)

    ใช้ start=1 เพื่อข้ามแท่งปัจจุบัน [0] ที่ยังวิ่งอยู่
    ทำให้ rates[-1] = แท่ง [1] ซึ่งปิดสมบูรณ์แล้วเสมอ

    Timing (M1 ตัวอย่าง):
      13:22:xx fill → รอแท่ง 13:22 ปิด
      13:23:xx → entry_bar=13:22, next_bar=None ✅ ประเมินแท่ง entry ได้
      13:24:xx → entry_bar=13:22, next_bar=13:23 ✅ ประเมิน waiting_next / waiting_bad ได้
    """
    if tf_val is None:
        tf_val = mt5.TIMEFRAME_M1
    # start=1: ข้ามแท่งปัจจุบัน [0] → rates[-1] = แท่ง [1] ที่ปิดแล้วเสมอ
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, 20)
    if rates is None or len(rates) < 2:
        return None, None

    fill_time = int(pos.time)

    tf_seconds = _get_tf_seconds(tf_val)

    # rates[-1] คือแท่งล่าสุดที่ "ปิดแล้ว"
    # entry_bar ใช้งานได้ทันทีเมื่อ fill_time อยู่ก่อนเวลาปิดของแท่งนี้
    latest_closed_open = int(rates[-1]["time"])
    latest_closed_close = latest_closed_open + tf_seconds
    if fill_time >= latest_closed_close:
        return None, None

    # หา entry_bar และ next_bar
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
    """ดึงราคาปัจจุบันฝั่งที่ใช้ตัดสินใจของ position"""
    tick = mt5.symbol_info_tick(SYMBOL)
    if tick:
        return float(tick.bid if pos_type == "BUY" else tick.ask)
    return 0.0


def _focus_side_presence(positions, pending_orders):
    """คืน (has_buy, has_sell) — นับรวม position + pending limit/stop"""
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
    อัปเดต marker ของ feature ('trail_sl' | 'entry_candle') ตามสภาพปัจจุบัน:
    - ไม่มี order ทั้ง 2 ฝั่ง  → reset marker เป็น None
    - marker ยัง None + มีฝั่งเดียว → ตั้ง marker เป็นฝั่งนั้น
    - marker ยัง None + มีทั้ง 2 ฝั่ง → รอให้ฝั่งใดฝั่งหนึ่งหายก่อน (return None)
    - marker มีค่าแล้ว → คงเดิม
    คืนค่า marker หลังอัปเดต
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
    ตรวจว่าฝั่ง frozen มี position ที่กำไร > threshold (+ TF ตรงถ้า separate) หรือไม่
    → True = ฝั่งตรงข้ามได้ทำงาน trail / ECM ตามปกติ
    feature: 'trail_sl' | 'entry_candle' (ใช้ config คนละชุด)
    """
    if feature == "trail_sl":
        points = int(getattr(config, "TRAIL_SL_FOCUS_NEW_POINTS", 100))
        tf_mode = getattr(config, "TRAIL_SL_FOCUS_NEW_TF_MODE", "separate")
    else:
        points = int(getattr(config, "ENTRY_CANDLE_FOCUS_NEW_POINTS", 100))
        tf_mode = getattr(config, "ENTRY_CANDLE_FOCUS_NEW_TF_MODE", "separate")
    points = points * config.points_scale()   # BTC = 4× ของ XAU (background)

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
    """คืน TF ที่ Trend Filter เปิดใช้งานและเกี่ยวข้องกับ order TF นี้"""
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
    ให้ Trail SL ข้าม Focus Opposite เฉพาะตอน trend filter เปลี่ยนฝั่งจริง:
    - SELL: ต้องเห็น BEAR/SIDEWAY -> BULL
    - BUY:  ต้องเห็น BULL/SIDEWAY -> BEAR
    UNKNOWN ไม่ถือเป็น trend ใหม่ และไม่ล้าง trend เดิม
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
            return True, f"Trend Filter {ref_tf}: {expected_prev} → {label}"
    return False, ""


def reset_focus_frozen_side(feature: str):
    """เรียกตอนผู้ใช้ toggle Focus Opposite OFF→ON ของฟีเจอร์นั้น"""
    if feature in _focus_frozen_side and _focus_frozen_side[feature] is not None:
        _focus_frozen_side[feature] = None
        try:
            save_runtime_state()
        except Exception:
            pass


def _get_spread_price():
    """ดึง spread เป็นหน่วยราคา"""
    info = mt5.symbol_info(SYMBOL)
    if not info:
        return 0.0
    try:
        return float(info.spread) * float(info.point)
    except Exception:
        return 0.0


def _fmt_bkk_ts(ts: int | float | None) -> str:
    """แปลง MT5 server timestamp เป็นเวลา Bangkok สำหรับแสดงผล"""
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
    """หลังปิด position แล้ว ให้ทำ flow Limit Sweep ต่อ (ยกเลิก limit / ตั้ง S8)"""
    now = now_bkk().strftime("%H:%M:%S")
    bar_close = float(bar["close"])
    bar_time = int(bar["time"])

    sh_info = _find_prev_swing_high(rates)
    sl_info = _find_prev_swing_low(rates)

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
            status = "✅" if ok_cancel else "❌"
            print(f"[{now}] 🧹 Sweep cancel {pos_type} LIMIT #{o.ticket} [{tf}] entry={o.price_open:.2f} {status}")
            pending_order_tf.pop(o.ticket, None)
        rng = f"{'LL' if pos_type == 'BUY' else 'L'}–{'H' if pos_type == 'BUY' else 'HH'}"
        print(f"[{now}] 🧹 Sweep keep #{kept_ticket} [{tf}] ใกล้ {'LL' if pos_type == 'BUY' else 'HH'}={target_price:.2f} (range {rng})")

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
                print(f"[{now}] 🧹 Sweep → S8 {s8_signal} LIMIT #{s8_ticket} [{tf}] "
                      f"Entry={s8_entry:.2f} SL={s8_sl:.2f} TP={s8_tp:.2f} "
                      f"{'LL' if pos_type == 'BUY' else 'HH'}={target_price:.2f}")
                await tg(app,
                    f"🧹 *Limit Sweep → S8*\n"
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


# ─────────────────────────────────────────────────────────────
async def check_entry_candle_quality(app):
    """
    ตรวจแท่งที่รับ order (ทุกท่า)

    BUY entry candle:
      เขียว body≥35%  → ✅ done
      เขียว body<35%  → ⏳ waiting_next
      แดง (ทุก body)  → ⚠️ waiting_bad: SL=swing_low−1.0, TP=entry.open

    SELL entry candle (สลับสี):
      แดง body≥35%   → ✅ done
      แดง body<35%   → ⏳ waiting_next
      เขียว (ทุก body) → ⚠️ waiting_bad: SL=swing_high+1.0, TP=entry.open

    waiting_bad (แท่งถัดไปจบ):
      BUY:  close≥entry → ปิด | close<entry → SL=next.low−1.0, TP=next.open → done
      SELL: close≤entry → ปิด | close>entry → SL=next.high+1.0, TP=next.open → done
    """
    global _fill_initialized, _last_meta_map_key
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

    # ── ครั้งแรกที่รัน: suppress เฉพาะ position เก่าจริง ๆ กัน re-notify ตอน restart
    # ถ้า position เพิ่ง fill มาใหม่ ๆ ยังควรได้ Limit Fill แม้ bot เพิ่งเริ่มทำงาน
    if not _fill_initialized:
        _fill_initialized = True
        now_ts = int(datetime.now(timezone.utc).timestamp())
        for p in positions:
            fill_age = max(0, now_ts - int(getattr(p, "time", 0) or 0))
            if fill_age >= _FILL_INIT_SUPPRESS_SEC:
                _fill_notified[p.ticket] = True

    now = now_bkk().strftime("%H:%M:%S")
    open_tickets = {p.ticket for p in positions}
    for t in list(_entry_bar_none_first.keys()):
        if t not in open_tickets:
            _entry_bar_none_first.pop(t, None)

    # ── Entry Candle Focus Opposite (frozen_side marker) ──
    # ฝั่งตรงกับ marker → skip ECM
    # ฝั่งตรงข้าม → ECM ทำงานเมื่อ gate ผ่าน (ฝั่ง frozen มีไม้กำไร > threshold + TF ผ่าน)
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
        sig_e    = "🟢" if pos_type == "BUY" else "🔴"
        state    = _entry_state.get(ticket)
        if _trade_debug_enabled():
            print(f"[{now}] 🔍 entry_check: {pos_type} {ticket} state={state} fvg={bool(fvg_order_tickets.get(ticket))} pos_tf={position_tf.get(ticket)}")

        # ── แจ้งเตือน Limit fill ครั้งแรก (ก่อน focus skip เพื่อไม่ให้หาย) ──
        fvg_info = fvg_order_tickets.get(ticket)
        pattern_name = position_pattern.get(ticket, "") or ""
        reverse_tag = " [Reverse]" if pattern_name.startswith("Reverse ") else ""
        if ticket not in _fill_notified:
            _fill_notified[ticket] = True
            fill_time = _fmt_bkk_ts(int(pos.time))
            _fill_tf = position_tf.get(ticket, fvg_info.get("tf", "M1") if fvg_info else "M1")
            try:
                from scanner import get_trend_label as _gtl
                _fill_trend = _gtl(_fill_tf)
            except Exception:
                _fill_trend = "?"
            log_event(
                "ENTRY_FILL",
                "Limit fill detected",
                ticket=ticket,
                side=pos_type,
                tf=_fill_tf,
                sid=position_sid.get(ticket),
                pattern=position_pattern.get(ticket, ""),
                price=pos.price_open,
                sl=pos.sl,
                tp=pos.tp,
                fill_time=fill_time,
                trend=_fill_trend,
            )
            await tg(app, (f"🔔 *Limit Fill — {pos_type}{reverse_tag}*\n"
                          f"{sig_e} Ticket:`{ticket}`\n"
                          f"🔖 Pattern: `{pattern_name or '-'}`\n"
                          f"📌 เปิดที่: `{pos.price_open:.2f}`\n"
                          f"🛑 SL: `{pos.sl:.2f}` | 🎯 TP: `{pos.tp:.2f}`\n"
                          f"🕐 Fill Time: `{fill_time}`"))
            print(f"🔔 [{now}] {pos_type} {ticket} fill={pos.price_open:.2f}")

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
                    # S8 fallback เดิม หรือ mode ปิด → ตั้งทันที
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
                            f"🛡 *ตั้ง SL หลัง Fill*\n"
                            f"{sig_e} Ticket:`{ticket}`\n"
                            f"🛑 SL: `0.00` → `{intended_sl:.2f}`\n"
                            f"เหตุผล: {_arm_fill_reason}"
                        ))
                        _s8_fill_sl.pop(ticket, None)
                    else:
                        print(f"⚠️ [{now}] fill arm SL failed ticket={ticket} sl={intended_sl:.2f} → retry next cycle")

        # ถ้า bot restart และ position มีกำไรมากพอ (>= 5 USD) → ผ่าน entry candle ไปแล้ว
        # ใช้ threshold สูงพอเพื่อกัน Limit fill ที่ได้กำไรทันทีเพียงเล็กน้อย
        if state is None and pos.profit >= 5.0:
            _entry_state[ticket] = "done"
            fvg_order_tickets.pop(ticket, None)
            save_runtime_state()
            print(f"♻️ [{now}] {pos_type} {ticket} profit={pos.profit:.2f} → auto done")
            continue

        # ดึง TF จาก position_tf (ทุกท่า) หรือ fvg_order_tickets (FVG)
        pos_tf   = position_tf.get(ticket)
        meta_source = "in_memory" if pos_tf else None

        # พยายามหา TF/SID จาก comment ก่อน เพราะแม่นกว่าการเดาจากราคา
        if not pos_tf and not fvg_info:
            c_tf, c_sid, c_source = _infer_position_meta_from_comment(pos)
            if c_tf:
                position_tf[ticket] = c_tf
                pos_tf = c_tf
                meta_source = c_source
            if ticket not in position_sid and c_sid is not None:
                position_sid[ticket] = c_sid

        # ถ้า position ใหม่ยังไม่มี position_tf → fallback จาก pending_order_tf ที่ราคาใกล้เคียง
        if not pos_tf and not fvg_info:
            for pticket, pinfo in list(pending_order_tf.items()):
                if isinstance(pinfo, dict):
                    # pending ที่ราคาใกล้กับ entry ของ position นี้
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
                        pos_tf = position_tf[ticket]
                        meta_source = f"pending_price_match:{pticket}"
                        break

        debug_tf = fvg_info.get("tf", "M1") if fvg_info else position_tf.get(ticket, pos_tf or "?")
        debug_sid = position_sid.get(ticket)
        debug_source = "fvg_memory" if fvg_info else (meta_source or "unknown")
        if _trade_debug_enabled():
            meta_key = f"{ticket}|{debug_tf}|{debug_sid}|{debug_source}"
            if meta_key != _last_meta_map_key:
                print(f"[{now}] 🧭 meta_map: ticket={ticket} tf={debug_tf} sid={debug_sid} source={debug_source}")
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

        # ── แจ้งเตือนแท่ง entry จบ พร้อม OHLC + body% ────────
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
            await tg(app, (f"🕯 *แท่ง Entry จบ — {pos_type}{reverse_tag}*\n"
                          f"{sig_e} Ticket:`{ticket}` [{_tf_name}]\n"
                          f"🔖 Pattern: `{pattern_name or '-'}`\n"
                          f"{_clr} O:`{_o:.2f}` H:`{_h:.2f}` L:`{_l:.2f}` C:`{_c:.2f}`\n"
                          f"📊 Body: `{_body_pct}%`\n"
                          f"🕐 Candle Close: `{_entry_close_time}`"))
            print(f"🕯  [{now}] {pos_type} {ticket} entry bar จบ body={_body_pct}%")

        def bar_info(bar):
            o = float(bar["open"]); h = float(bar["high"])
            l = float(bar["low"]);  c = float(bar["close"])
            rng = h - l
            return c > o, abs(c-o)/rng if rng > 0 else 0, round(abs(c-o)/rng*100 if rng > 0 else 0)

        spread_price = _get_spread_price()
        current_price = float(entry_bar["close"])

        if state is None:
            # ── ตรวจแท่ง entry ────────────────────────────────
            bull, body_pct, body_pct_int = bar_info(entry_bar)

            # หา prev_bar (แท่งก่อน entry_bar)
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

            # ── Reverse position: เงื่อนไขปิดพิเศษ ──────────────
            if ticket in _reverse_tickets:
                if pos_type == "SELL" and bull and current_price > prev_high:
                    # SELL reverse: เขียว + close > prev high → ปิดทันที
                    reason_rev = f"Reverse SELL เขียว close={current_price:.2f} > prev_high={prev_high:.2f}"
                    ok_rev, cp_rev = _close_position(pos, pos_type, "reverse entry green > prev high")
                    if ok_rev:
                        _entry_state[ticket] = "done"
                        _reverse_tickets.discard(ticket)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "reverse_close", ticket=ticket, side=pos_type, state="done", close_price=cp_rev, reason=reason_rev)
                        await tg(app, f"❌ *ปิด SELL Reverse — เขียว > prev High*\n🔴 Ticket:`{ticket}` ปิดที่`{cp_rev}`\n📊 Close:`{current_price:.2f}` > PrevHigh:`{prev_high:.2f}`")
                        print(f"❌ [{now}] {reason_rev} → ปิดที่ {cp_rev}")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                    continue
                elif pos_type == "BUY" and not bull and current_price < prev_low:
                    # BUY reverse: แดง + close < prev low → ปิดทันที
                    reason_rev = f"Reverse BUY แดง close={current_price:.2f} < prev_low={prev_low:.2f}"
                    ok_rev, cp_rev = _close_position(pos, pos_type, "reverse entry red < prev low")
                    if ok_rev:
                        _entry_state[ticket] = "done"
                        _reverse_tickets.discard(ticket)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "reverse_close", ticket=ticket, side=pos_type, state="done", close_price=cp_rev, reason=reason_rev)
                        await tg(app, f"❌ *ปิด BUY Reverse — แดง < prev Low*\n🟢 Ticket:`{ticket}` ปิดที่`{cp_rev}`\n📊 Close:`{current_price:.2f}` < PrevLow:`{prev_low:.2f}`")
                        print(f"❌ [{now}] {reason_rev} → ปิดที่ {cp_rev}")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                    continue
                else:
                    # Reverse position: entry candle ปกติ → done
                    if config.ENTRY_CANDLE_MODE == "close_percentage" and current_price > pos.price_open:
                        new_sl = round(float(pos.price_open) + spread_price, 2)
                        _apply_entry_sl_tp(pos, new_sl, pos.tp)
                    _entry_state[ticket] = "done"
                    _reverse_tickets.discard(ticket)
                    save_runtime_state()
                    print(f"✅ [{now}] Reverse {pos_type} {ticket} entry candle OK → done")
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
                    print(f"✅ [{now}] Reverse {pos_type} {ticket} entry done SL={reverse_sl} ({reverse_note})")
                    continue

            if pos_type == "BUY":
                if bull and body_pct >= 0.35:
                    if config.ENTRY_CANDLE_MODE == "close_percentage" and current_price > pos.price_open:
                        new_sl = round(float(pos.price_open) + spread_price, 2)
                        ok = _apply_entry_sl_tp(pos, new_sl, pos.tp)
                        if not ok:
                            print(f"[ENTRY_CLOSE_MODE] BUY modify SL failed ticket={ticket} sl={new_sl} → retry next cycle")
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
                            print(f"[ENTRY_CLOSE_MODE] BUY modify SL failed ticket={ticket} sl={new_sl} → retry next cycle")
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
                            print(f"[ENTRY_CLOSE_MODE] BUY modify SL failed ticket={ticket} sl={new_sl} → retry next cycle")
                            continue
                        _entry_state[ticket] = "done"
                        fvg_order_tickets.pop(ticket, None)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "done_sl_protect", ticket=ticket, side=pos_type, state="done", sl=new_sl, reason=f"red body={body_pct_int}% ask={ask_price:.2f}>entry+spread={entry_plus_spread:.2f}")
                        await tg(app, f"🛡️ *BUY Entry แดง — SL Protect*\n{sig_e} Ticket:`{ticket}`\n🛑 SL: `{new_sl}` (Entry+Spread)\n📊 Ask: `{ask_price:.2f}` > Entry+Spread: `{entry_plus_spread:.2f}`\nBody: `{body_pct_int}%`")
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
                        reason = f"entry_red body={body_pct_int}% ask≤entry+spread close_percentage"
                        ok, cp = _close_position(pos, pos_type, "entry red ask<=entry+spread")
                        if ok:
                            _entry_state[ticket] = "done"
                            fvg_order_tickets.pop(ticket, None)
                            save_runtime_state()
                            log_event("ENTRY_QUALITY", "close_immediate", ticket=ticket, side=pos_type, state="done", close_price=cp, candle_close=f"{current_price:.2f}", reason=reason)
                            await tg(app, f"❌ *CLOSE BUY - Entry แดง ask≤entry+spread*\n{sig_e} Ticket:`{ticket}`\nAsk: `{ask_price}`\nEntry+Spread: `{entry_plus_spread:.2f}`\nExecuted Close: `{cp}`\nBody: `{body_pct_int}%`")
                            print(f"[CLOSE_IMMEDIATE] BUY ticket={ticket} reason={reason} close={cp}")
                            if config.LIMIT_SWEEP:
                                tf_name = position_tf.get(ticket, "M1")
                                lookback = TF_LOOKBACK.get(tf_name, SWING_LOOKBACK)
                                rates_sweep = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, lookback + 6)
                                if rates_sweep is not None and len(rates_sweep) >= 6:
                                    reason_detail = f"แท่งจบแดง body={body_pct_int}% ask≤entry+spread ปิดทันที"
                                    await _run_limit_sweep_followup(
                                        app, ticket, pos_type, tf_name, rates_sweep, entry_bar, prev_bar, reason_detail
                                    )
                            continue
                        else:
                            _entry_state[ticket] = "closing_fail"
                            save_runtime_state()
                            await tg(app, f"⚠️ *ปิด BUY ไม่สำเร็จ (entry แดง ask≤entry+spread)*\n{sig_e} Ticket:`{ticket}`")

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
                        # close_percentage: ปิดทันทีอย่างเดียว ไม่เปิด reverse market/limit
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
                                    await tg(app, f"🔄 *เปิด SELL Market (Reverse)*\n🔴 Ticket:`{rev_ticket}`\n📌 Entry: `{float(tick_r.bid):.2f}`\n🛑 SL: `{mkt_sl}` (Entry High+SL_BUFFER)\n🎯 TP: `{rev_tp}` (Swing Low)\n📊 TF: `{tf_name}`\n🔖 จาก: `{ticket}`")
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
                                await tg(app, f"🔄 *ตั้ง SELL LIMIT (Reverse)*\n🔴 Ticket:`{rev_order}`\n📌 Entry: `{lim_entry:.2f}` (High+17%)\n🛑 SL: `{lim_sl:.2f}` (High+31%)\n🎯 TP: `{rev_tp}` (Swing Low)\n📊 TF: `{tf_name}`\n🔖 จาก: `{ticket}`")
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
                    swing_info = _find_prev_swing_low(rates_swing) if rates_swing is not None else None
                    swing_sl = round(swing_info["price"] - 1.0, 2) if swing_info else round(entry_low - 1.0, 2)
                    bad_tp = round(float(entry_bar["open"]) - spread_price, 2)
                    reason = f"แดง High>{prev_high:.2f}" if entry_high > prev_high else (
                        f"แดง body={body_pct_int}%≥65%" if body_pct >= 0.65 else f"แดง body={body_pct_int}%<65%")
                    ok = _apply_entry_sl_tp(pos, swing_sl, bad_tp)
                    _entry_state[ticket] = "waiting_bad"
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "waiting_bad", ticket=ticket, side=pos_type, state="waiting_bad", reason=reason, sl=swing_sl, tp=bad_tp)
                    if ok:
                        title = f"⚠️ *BUY Entry แดง — waiting\\_bad*\n{sig_e} Ticket:`{ticket}` | {reason}"
                        msg = _entry_update_msg(title, sig_e, ticket, swing_sl, "swing low", bad_tp, "entry open")
                        await tg(app, msg)
                    print(f"⏳ [{now}] BUY {ticket} {reason} → waiting_bad SL={swing_sl} TP={bad_tp}")

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
                    print(f"[ENTRY] BUY {ticket} red entry but current>{pos.price_open:.2f} → SL={new_sl}")

            else:  # SELL
                if not bull and body_pct >= 0.35:
                    if config.ENTRY_CANDLE_MODE == "close_percentage" and current_price < pos.price_open:
                        new_sl = round(float(pos.price_open) - spread_price, 2)
                        ok = _apply_entry_sl_tp(pos, new_sl, pos.tp)
                        if not ok:
                            print(f"[ENTRY_CLOSE_MODE] SELL modify SL failed ticket={ticket} sl={new_sl} → retry next cycle")
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
                            print(f"[ENTRY_CLOSE_MODE] SELL modify SL failed ticket={ticket} sl={new_sl} → retry next cycle")
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
                            print(f"[ENTRY_CLOSE_MODE] SELL modify SL failed ticket={ticket} sl={new_sl} → retry next cycle")
                            continue
                        _entry_state[ticket] = "done"
                        fvg_order_tickets.pop(ticket, None)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "done_sl_protect", ticket=ticket, side=pos_type, state="done", sl=new_sl, reason=f"green body={body_pct_int}% bid={bid_price:.2f}<entry-spread={entry_minus_spread:.2f}")
                        await tg(app, f"🛡️ *SELL Entry เขียว — SL Protect*\n{sig_e} Ticket:`{ticket}`\n🛑 SL: `{new_sl}` (Entry-Spread)\n📊 Bid: `{bid_price:.2f}` < Entry-Spread: `{entry_minus_spread:.2f}`\nBody: `{body_pct_int}%`")
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
                        reason = f"entry_green body={body_pct_int}% bid≥entry-spread close_percentage"
                        ok, cp = _close_position(pos, pos_type, "entry green bid>=entry-spread")
                        if ok:
                            _entry_state[ticket] = "done"
                            fvg_order_tickets.pop(ticket, None)
                            save_runtime_state()
                            log_event("ENTRY_QUALITY", "close_immediate", ticket=ticket, side=pos_type, state="done", close_price=cp, candle_close=f"{current_price:.2f}", reason=reason)
                            await tg(app, f"❌ *CLOSE SELL - Entry เขียว bid≥entry-spread*\n{sig_e} Ticket:`{ticket}`\nBid: `{bid_price}`\nEntry-Spread: `{entry_minus_spread:.2f}`\nExecuted Close: `{cp}`\nBody: `{body_pct_int}%`")
                            print(f"[CLOSE_IMMEDIATE] SELL ticket={ticket} reason={reason} close={cp}")
                            if config.LIMIT_SWEEP:
                                tf_name = position_tf.get(ticket, "M1")
                                lookback = TF_LOOKBACK.get(tf_name, SWING_LOOKBACK)
                                rates_sweep = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, lookback + 6)
                                if rates_sweep is not None and len(rates_sweep) >= 6:
                                    reason_detail = f"แท่งจบเขียว body={body_pct_int}% bid≥entry-spread ปิดทันที"
                                    await _run_limit_sweep_followup(
                                        app, ticket, pos_type, tf_name, rates_sweep, entry_bar, prev_bar, reason_detail
                                    )
                            continue
                        else:
                            _entry_state[ticket] = "closing_fail"
                            save_runtime_state()
                            await tg(app, f"⚠️ *ปิด SELL ไม่สำเร็จ (entry เขียว bid≥entry-spread)*\n{sig_e} Ticket:`{ticket}`")

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
                        # close_percentage: ปิดทันทีอย่างเดียว ไม่เปิด reverse market/limit
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
                                    await tg(app, f"🔄 *เปิด BUY Market (Reverse)*\n🟢 Ticket:`{rev_ticket}`\n📌 Entry: `{float(tick_r.ask):.2f}`\n🛑 SL: `{mkt_sl}` (Entry Low-SL_BUFFER)\n🎯 TP: `{rev_tp}` (Swing High)\n📊 TF: `{tf_name}`\n🔖 จาก: `{ticket}`")
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
                                await tg(app, f"🔄 *ตั้ง BUY LIMIT (Reverse)*\n🟢 Ticket:`{rev_order}`\n📌 Entry: `{lim_entry:.2f}` (Low-17%)\n🛑 SL: `{lim_sl:.2f}` (Low-31%)\n🎯 TP: `{rev_tp}` (Swing High)\n📊 TF: `{tf_name}`\n🔖 จาก: `{ticket}`")
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
                    swing_info = _find_prev_swing_high(rates_swing) if rates_swing is not None else None
                    swing_sl = round(swing_info["price"] + 1.0, 2) if swing_info else round(entry_high + 1.0, 2)
                    bad_tp = round(float(entry_bar["open"]) + spread_price, 2)
                    reason = f"เขียว Low<{prev_low:.2f}" if entry_low < prev_low else (
                        f"เขียว body={body_pct_int}%≥65%" if body_pct >= 0.65 else f"เขียว body={body_pct_int}%<65%")
                    ok = _apply_entry_sl_tp(pos, swing_sl, bad_tp)
                    _entry_state[ticket] = "waiting_bad"
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "waiting_bad", ticket=ticket, side=pos_type, state="waiting_bad", reason=reason, sl=swing_sl, tp=bad_tp)
                    if ok:
                        title = f"⚠️ *SELL Entry เขียว — waiting\\_bad*\n{sig_e} Ticket:`{ticket}` | {reason}"
                        msg = _entry_update_msg(title, sig_e, ticket, swing_sl, "swing high", bad_tp, "entry open")
                        await tg(app, msg)
                    print(f"⏳ [{now}] SELL {ticket} {reason} → waiting_bad SL={swing_sl} TP={bad_tp}")

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
                    print(f"✅ [{now}] SELL {ticket} green entry but current<{pos.price_open:.2f} -> SL={new_sl}")

        elif state == "closing_fail":
            # ── retry close (silent) ──────────────────────────────
            ok, cp = _close_position(pos, pos_type, "retry_close")
            if ok:
                _entry_state[ticket] = "done"
                save_runtime_state()
                await tg(app, f"✅ *retry ปิด {pos_type} สำเร็จ*\n{sig_e} Ticket:`{ticket}` ปิดที่`{cp}`")
                print(f"✅ [{now}] retry close {pos_type} {ticket} สำเร็จ @ {cp}")
            else:
                print(f"❌ [{now}] retry close {pos_type} {ticket} ยังไม่สำเร็จ")
            continue

        elif state == "waiting_next":
            # ── แท่งถัดจาก entry ─────────────────────────────────
            if next_bar is None:
                continue

            bull_next, _, _ = bar_info(next_bar)
            next_c = float(next_bar["close"])
            entry_h = float(entry_bar["high"])
            entry_l = float(entry_bar["low"])

            if pos_type == "BUY":
                # ปิดเมื่อ: แดง + Close < Low[entry]
                if not bull_next and next_c < entry_l:
                    ok, cp = _close_position(pos, pos_type, "waiting_next: red close < entry low")
                    if ok:
                        _entry_state[ticket] = "done"
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "waiting_next close", ticket=ticket, side=pos_type, state="done", close_price=cp, reason="red close < entry low")
                        await tg(app, f"❌ *ปิด BUY — แดง Close<Low[entry]*\n{sig_e} Ticket:`{ticket}` ปิดที่`{cp}`")
                        print(f"❌ [{now}] ปิด BUY {ticket} แดง Close:{next_c:.2f}<Low[entry]:{entry_l:.2f}")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                        await tg(app, f"⚠️ *ปิด BUY ไม่สำเร็จ (waiting_next)*\n{sig_e} Ticket:`{ticket}`")
                else:
                    # ผ่าน → ตั้ง SL=next.low−1.0, TP=next.open (เหมือน waiting_bad)
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
                        tp_note = "entry (next open ต่ำกว่า entry)"
                    ok = _apply_entry_sl_tp(pos, new_sl, new_tp)
                    if not ok:
                        print(f"⚠️ [{now}] BUY {ticket} waiting_next modify SL failed sl={new_sl} → retry next cycle")
                        continue
                    _entry_state[ticket] = "done"
                    fvg_order_tickets.pop(ticket, None)
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "waiting_next done", ticket=ticket, side=pos_type, state="done", sl=new_sl, tp=new_tp, reason=tp_note)
                    await tg(app, _entry_update_msg(
                        "✅ *BUY waiting\\_next → done*",
                        sig_e, ticket, new_sl, sl_note, new_tp, tp_note
                    ))
                    print(f"✅ [{now}] BUY {ticket} waiting_next→done SL={new_sl} TP={new_tp} ({sl_note}, {tp_note})")

            else:  # SELL
                # ปิดเมื่อ: เขียว + Close > High[entry]
                if bull_next and next_c > entry_h:
                    ok, cp = _close_position(pos, pos_type, "waiting_next: green close > entry high")
                    if ok:
                        _entry_state[ticket] = "done"
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "waiting_next close", ticket=ticket, side=pos_type, state="done", close_price=cp, reason="green close > entry high")
                        await tg(app, f"❌ *ปิด SELL — เขียว Close>High[entry]*\n{sig_e} Ticket:`{ticket}` ปิดที่`{cp}`")
                        print(f"❌ [{now}] ปิด SELL {ticket} เขียว Close:{next_c:.2f}>High[entry]:{entry_h:.2f}")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                        await tg(app, f"⚠️ *ปิด SELL ไม่สำเร็จ (waiting_next)*\n{sig_e} Ticket:`{ticket}`")
                else:
                    # ผ่าน → ตั้ง SL=next.high+1.0, TP=next.open (เหมือน waiting_bad)
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
                        tp_note = "entry (next open สูงกว่า entry)"
                    ok = _apply_entry_sl_tp(pos, new_sl, new_tp)
                    if not ok:
                        print(f"⚠️ [{now}] SELL {ticket} waiting_next modify SL failed sl={new_sl} → retry next cycle")
                        continue
                    _entry_state[ticket] = "done"
                    fvg_order_tickets.pop(ticket, None)
                    save_runtime_state()
                    log_event("ENTRY_QUALITY", "waiting_next done", ticket=ticket, side=pos_type, state="done", sl=new_sl, tp=new_tp, reason=tp_note)
                    await tg(app, _entry_update_msg(
                        "✅ *SELL waiting\\_next → done*",
                        sig_e, ticket, new_sl, sl_note, new_tp, tp_note
                    ))
                    print(f"✅ [{now}] SELL {ticket} waiting_next→done SL={new_sl} TP={new_tp} ({sl_note}, {tp_note})")

        elif state == "waiting_bad":
            # ── แท่งถัดจาก entry (entry แดงสำหรับ BUY / เขียวสำหรับ SELL) ──
            if next_bar is None:
                continue

            next_c = float(next_bar["close"])
            next_h = float(next_bar["high"])
            next_l = float(next_bar["low"])

            if pos_type == "BUY":
                orig_tp = pos.tp  # TP เดิมของ order
                if next_c >= pos.price_open:
                    print(f"[{now}] WAITING_BAD_CLOSE BUY ticket={ticket} next_close={next_c:.2f} entry={pos.price_open:.2f} next_high={next_h:.2f} next_low={next_l:.2f}")
                    ok, cp = _close_position(pos, pos_type, "waiting_bad: close >= entry")
                    if ok:
                        _entry_state[ticket] = "done"
                        fvg_order_tickets.pop(ticket, None)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "waiting_bad close", ticket=ticket, side=pos_type, state="done", close_price=cp, reason="close >= entry")
                        await tg(app, f"❌ *ปิด BUY → waiting\\_bad close>=entry*\n{sig_e} Ticket:`{ticket}` ปิดที่`{cp}`")
                        print(f"❌ [{now}] ปิด BUY {ticket} waiting_bad close:{next_c:.2f}>=entry:{pos.price_open:.2f}")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                        await tg(app, f"⚠️ *ปิด BUY ไม่สำเร็จ (waiting_bad)*\n{sig_e} Ticket:`{ticket}`")
                    continue
                    # close >= entry → SL = entry + 0.5, TP เดิม
                    new_sl = round(pos.price_open + 0.5, 2)
                    new_tp = orig_tp
                    sl_note = "entry+0.5"
                else:
                    # close < entry → SL = next.low − 1.0, TP เดิม
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
                    print(f"⚠️ [{now}] BUY {ticket} waiting_bad modify SL failed sl={new_sl} → retry next cycle")
                    continue
                _entry_state[ticket] = "done"
                fvg_order_tickets.pop(ticket, None)
                save_runtime_state()
                log_event("ENTRY_QUALITY", "waiting_bad done", ticket=ticket, side=pos_type, state="done", sl=new_sl, tp=new_tp, reason=sl_note)
                await tg(app, _entry_update_msg(
                    "✅ *BUY waiting\\_bad → done*",
                    sig_e, ticket, new_sl, sl_note, new_tp
                ))
                print(f"✅ [{now}] BUY {ticket} waiting_bad→done SL={new_sl} TP={new_tp} ({sl_note})")

            else:  # SELL
                orig_tp = pos.tp  # TP เดิมของ order
                if next_c <= pos.price_open:
                    print(f"[{now}] WAITING_BAD_CLOSE SELL ticket={ticket} next_close={next_c:.2f} entry={pos.price_open:.2f} next_high={next_h:.2f} next_low={next_l:.2f}")
                    ok, cp = _close_position(pos, pos_type, "waiting_bad: close <= entry")
                    if ok:
                        _entry_state[ticket] = "done"
                        fvg_order_tickets.pop(ticket, None)
                        save_runtime_state()
                        log_event("ENTRY_QUALITY", "waiting_bad close", ticket=ticket, side=pos_type, state="done", close_price=cp, reason="close <= entry")
                        await tg(app, f"❌ *ปิด SELL → waiting\\_bad close<=entry*\n{sig_e} Ticket:`{ticket}` ปิดที่`{cp}`")
                        print(f"❌ [{now}] ปิด SELL {ticket} waiting_bad close:{next_c:.2f}<=entry:{pos.price_open:.2f}")
                    else:
                        _entry_state[ticket] = "closing_fail"
                        save_runtime_state()
                        await tg(app, f"⚠️ *ปิด SELL ไม่สำเร็จ (waiting_bad)*\n{sig_e} Ticket:`{ticket}`")
                    continue
                    # close <= entry → SL = entry − 0.5, TP เดิม
                    new_sl = round(pos.price_open - 0.5, 2)
                    new_tp = orig_tp
                    sl_note = "entry-0.5"
                else:
                    # close > entry → SL = next.high + 1.0, TP เดิม
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
                    print(f"⚠️ [{now}] SELL {ticket} waiting_bad modify SL failed sl={new_sl} → retry next cycle")
                    continue
                _entry_state[ticket] = "done"
                fvg_order_tickets.pop(ticket, None)
                save_runtime_state()
                log_event("ENTRY_QUALITY", "waiting_bad done", ticket=ticket, side=pos_type, state="done", sl=new_sl, tp=new_tp, reason=sl_note)
                await tg(app, _entry_update_msg(
                    "✅ *SELL waiting\\_bad → done*",
                    sig_e, ticket, new_sl, sl_note, new_tp
                ))
                print(f"✅ [{now}] SELL {ticket} waiting_bad→done SL={new_sl} TP={new_tp} ({sl_note})")


# ─────────────────────────────────────────────────────────────
async def check_engulf_trail_sl(app):
    """
    Trail SL แบบ Group TF:
    phase 1: ตรวจ Engulf ใน TF เล็กกว่า (group[1:]) → เลื่อน SL → เข้า phase 2
    phase 2: ตรวจ Engulf ใน TF ของ order เอง (group[0]) → เลื่อน SL → จบ

    โหมด combined:
    - รวม phase ตาม group TF
    - ตรวจทุก TF ใน group พร้อมกันทุกครั้ง
    - เลื่อน SL ต่อเนื่องเมื่อเจอ engulf ที่ให้ SL ดีขึ้น

    group ตาม TRAIL_GROUPS:
      D1  → [D1, H12, H4]
      H12 → [H12, H4, H1]
      ...
      M1  → [M1]
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

    # cleanup tickets ที่ปิดไปแล้ว
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

    now = now_bkk().strftime("%H:%M:%S")

    # ── Trail SL Focus Opposite (frozen_side marker) ──
    # ฝั่งตรงกับ marker → freeze ทุกไม้ (ไม่ trail)
    # ฝั่งตรงข้าม → trail ได้เมื่อ gate ผ่าน (ฝั่ง frozen มีไม้ที่กำไร > threshold + TF ผ่าน)
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

        # หา TF ของ order
        fvg_info = fvg_order_tickets.get(ticket)
        order_tf = position_tf.get(ticket, "M1")
        if fvg_info:
            order_tf = fvg_info.get("tf", "M1")

        if not config.TRAIL_SL_IMMEDIATE and _entry_state.get(ticket) != "done":
            continue

        # Trail SL เฉพาะเมื่อราคาอยู่เหนือ entry (BUY) หรือต่ำกว่า entry (SELL)
        tick = mt5.symbol_info_tick(SYMBOL)
        if tick:
            if pos_type == "BUY" and tick.bid <= pos.price_open:
                continue
            if pos_type == "SELL" and tick.ask >= pos.price_open:
                continue

        trend_override, trend_override_reason = _trend_filter_trail_override(ticket, pos_type, order_tf)
        if ticket in focus_skip_tickets and not trend_override:
            continue

        mode = getattr(config, "TRAIL_SL_ENGULF_MODE", "separate")

        # init trail state
        if ticket not in _trail_state:
            group = TRAIL_GROUPS.get(order_tf, [order_tf])
            # combined = ตรวจทุก TF ใน group ต่อเนื่อง ไม่จบที่ phase 2
            if mode == "combined":
                phase = 0
            else:
                # phase 1 ถ้ามี TF เล็กกว่า, phase 2 ถ้า M1 หรือ group มีแค่ตัวเอง
                phase = 1 if len(group) > 1 else 2
            _trail_state[ticket] = {"phase": phase, "order_tf": order_tf}

        state    = _trail_state[ticket]
        phase    = state["phase"]
        group    = TRAIL_GROUPS.get(order_tf, [order_tf])

        # phase 2 จบแล้ว → ไม่ trail อีก (เฉพาะโหมดแยก phase)
        if mode != "combined" and phase > 2:
            continue

        # กำหนด TF ที่ตรวจในแต่ละ phase
        if mode == "combined":
            check_tfs = group
        elif phase == 1:
            # ตรวจ TF เล็กกว่า (group[1:]) — เช่น H4 order → ตรวจ H1, M30
            check_tfs = group[1:] if len(group) > 1 else group
        else:
            # phase 2: ตรวจแค่ TF ของ order เอง
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

            # หาแท่ง entry bar
            entry_bar_time = 0
            for r in rates:
                t = int(r["time"])
                if t <= pos.time and t > entry_bar_time:
                    entry_bar_time = t
            if entry_bar_time == 0:
                continue

            bars_after = [r for r in rates if int(r["time"]) >= entry_bar_time]
            if len(bars_after) < 2:
                continue

            # นับแท่ง
            cur_bar_time = int(bars_after[-1]["time"])
            key_last = f"{ticket}_{tf_name}_last"
            if cur_bar_time != _bar_count.get(key_last, 0):
                _bar_count[key_last] = cur_bar_time
                _bar_count[f"{ticket}_{tf_name}"] = _bar_count.get(f"{ticket}_{tf_name}", 0) + 1

            # Loop หา Engulf ที่ดีที่สุดใน TF นี้
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
                # เลือก TF ที่ให้ SL ดีที่สุด
                if pos_type == "BUY" and (new_sl == 0 or current_sl > new_sl):
                    new_sl = current_sl; engulf_found = True
                    engulf_tf = tf_name; label = f"Trail SL [{tf_name}] Engulf"
                elif pos_type == "SELL" and (new_sl == 0 or current_sl < new_sl):
                    new_sl = current_sl; engulf_found = True
                    engulf_tf = tf_name; label = f"Trail SL [{tf_name}] Engulf"

        # SL ปกป้อง ถ้าไม่เจอ Engulf ใน 3 แท่ง (เฉพาะ phase 1 และ TF หลัก)
        if not engulf_found:
            main_tf  = group[0]
            key_cnt  = f"{ticket}_{main_tf}"
            bar_cnt  = _bar_count.get(key_cnt, 0)
            if bar_cnt >= 3:
                entry_price = pos.price_open
                if pos_type == "BUY":
                    safe = round(entry_price + 0.5, 2)
                    if safe > pos.sl:
                        new_sl = safe; label = f"SL ปกป้อง [{main_tf}] +50pt"
                else:
                    safe = round(entry_price - 0.5, 2)
                    if pos.sl == 0 or safe < pos.sl:
                        new_sl = safe; label = f"SL ปกป้อง [{main_tf}] −50pt"

        # ── ตรวจว่าราคาปัจจุบันปิดดีกว่า entry ไหม ──────────────
        # ใช้แท่งล่าสุดที่ปิดแล้ว (ดึง TF ของ order)
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

                # เลื่อน phase เฉพาะเมื่อราคาปิดดีกว่า entry แล้ว
                if engulf_found and mode == "combined":
                    phase_note = f"combined mode (เจอใน {engulf_tf}, เลื่อน SL ต่อเนื่อง)"
                elif engulf_found:
                    if phase == 1:
                        if price_past_entry:
                            _trail_state[ticket]["phase"] = 2
                            save_runtime_state()
                            phase_note = f"phase 1→2 (เจอใน {engulf_tf}, ราคาผ่าน entry)"
                        else:
                            phase_note = f"phase 1 ค้าง (เจอใน {engulf_tf}, รอราคาผ่าน entry)"
                    else:  # phase 2
                        if price_past_entry:
                            _trail_state[ticket]["phase"] = 3  # จบ
                            save_runtime_state()
                            phase_note = f"phase 2→จบ (เจอใน {engulf_tf}, ราคาผ่าน entry)"
                        else:
                            phase_note = f"phase 2 ค้าง (เจอใน {engulf_tf}, รอราคาผ่าน entry)"
                else:
                    phase_note = "SL ปกป้อง"
                if trend_override:
                    phase_note = f"{phase_note} | override {trend_override_reason}"

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
                    await tg(app, (f"📐 *{label} — {pos_type}*\n"
                              f"{sig_e} Ticket:`{ticket}` [{order_tf}]\n"
                              f"🛑 SL: `{old_sl}` → `{new_sl}`\n"
                              f"📋 {phase_note}"))
                    _last_trail_tg_key = trail_tg_key
                print(f"📐 [{now}] {label} {pos_type} {ticket}: {old_sl}→{new_sl} | {phase_note}")


# ─────────────────────────────────────────────────────────────
async def check_opposite_order_tp(app):
    """
    ฝั่งตรงข้าม TP (จับคู่เฉพาะ TF เดียวกัน):
    1) BUY position กำไร + SELL limit (TF เดียวกัน) → TP ของ BUY = Entry SELL limit
    2) SELL position กำไร + BUY limit (TF เดียวกัน) → TP ของ SELL = Entry BUY limit
    3) มีทั้ง BUY + SELL position TF เดียวกัน → ปิดตัวที่เปิดก่อน (ตัวเก่า)
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
    buy_pos  = [p for p in positions if p.type == mt5.ORDER_TYPE_BUY]
    sell_pos = [p for p in positions if p.type == mt5.ORDER_TYPE_SELL]

    def _get_order_tf(ticket):
        info = pending_order_tf.get(ticket)
        if isinstance(info, dict):
            return info.get("tf")
        return info

    opp_mode = config.OPPOSITE_ORDER_MODE  # "tp_close" | "sl_protect"

    if pending and opp_mode == "tp_close":
        buy_lim  = [o for o in pending if o.type == mt5.ORDER_TYPE_BUY_LIMIT]
        sell_lim = [o for o in pending if o.type == mt5.ORDER_TYPE_SELL_LIMIT]

        # BUY position กำไร + SELL limit TF เดียวกัน → TP ของ BUY = Entry SELL limit
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
                            print(f"🔄 [{now}] BUY {pos.ticket} [{pos_tf}] TP→{se}")

        # SELL position กำไร + BUY limit TF เดียวกัน → TP ของ SELL = Entry BUY limit
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
                            print(f"🔄 [{now}] SELL {pos.ticket} [{pos_tf}] TP→{be}")

    # มีทั้ง BUY + SELL position TF เดียวกัน
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
                    # ── tp_close: ปิดตัวที่เปิดก่อน (ตัวเก่า) ──
                    if bp.time > sp.time:
                        ok, cp = _close_position(sp, "SELL", f"Close SELL - BUY filled [{bp_tf}]")
                        if ok:
                            await tg(app, (f"🔒 *ปิด SELL — BUY Limit Fill [{bp_tf}]*\n"
                                      f"🔴 Ticket:`{sp.ticket}` ปิดที่`{cp}`"))
                            print(f"🔒 [{now}] ปิด SELL {sp.ticket} BUY fill [{bp_tf}]")
                    elif sp.time > bp.time:
                        ok, cp = _close_position(bp, "BUY", f"Close BUY - SELL filled [{bp_tf}]")
                        if ok:
                            await tg(app, (f"🔒 *ปิด BUY — SELL Limit Fill [{bp_tf}]*\n"
                                      f"🟢 Ticket:`{bp.ticket}` ปิดที่`{cp}`"))
                            print(f"🔒 [{now}] ปิด BUY {bp.ticket} SELL fill [{bp_tf}]")

                else:
                    # ── sl_protect: ตั้ง SL = entry ± spread (ไม่ปิด) ──
                    if bp.time > sp.time:
                        # BUY fill ทีหลัง → ตั้ง SL ของ SELL = entry - spread
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
                                    await tg(app, (f"🛡  *SELL SL Protect — BUY Fill [{bp_tf}]*\n"
                                                  f"🔴 Ticket:`{sp.ticket}`\n"
                                                  f"🛑 SL: `{old_sl:.2f}` → `{new_sl:.2f}` (entry−spread)"))
                                    _last_sl_protect_tg_key = protect_tg_key
                                print(f"🛡  [{now}] SELL {sp.ticket} SL→{new_sl} (entry={sp.price_open:.2f}−spread={spread:.2f})")
                    elif sp.time > bp.time:
                        # SELL fill ทีหลัง → ตั้ง SL ของ BUY = entry + spread
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
                                    await tg(app, (f"🛡  *BUY SL Protect — SELL Fill [{bp_tf}]*\n"
                                                  f"🟢 Ticket:`{bp.ticket}`\n"
                                                  f"🛑 SL: `{old_sl:.2f}` → `{new_sl:.2f}` (entry+spread)"))
                                    _last_sl_protect_tg_key = protect_tg_key
                                print(f"🛡  [{now}] BUY {bp.ticket} SL→{new_sl} (entry={bp.price_open:.2f}+spread={spread:.2f})")


async def check_breakeven_tp(app):
    """
    ทุกท่า: หลังแท่ง entry ถ้าราคาลงต่ำกว่า entry (BUY) แล้วมีแท่งปิดแดงตำหนิหรือกลืนกิน
    → ตั้ง TP = Entry (breakeven)

    BUY:
      ราคาต่ำกว่า entry AND แท่งล่าสุดปิดแดง:
        - กลืนกิน: Close < Low[prev]
        - ตำหนิ:   Low[cur] < Low[prev] และ Close อยู่ใน body ของ prev

    SELL: สลับสี
      ราคาสูงกว่า entry AND แท่งล่าสุดปิดเขียว:
        - กลืนกิน: Close > High[prev]
        - ตำหนิ:   High[cur] > High[prev] และ Close อยู่ใน body ของ prev
    """
    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        return

    now = now_bkk().strftime("%H:%M:%S")

    for pos in positions:
        ticket   = pos.ticket
        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        entry    = pos.price_open

        # รันเฉพาะ order ที่ผ่าน entry candle แล้ว
        if _entry_state.get(ticket) != "done":
            continue

        # TP = entry แล้ว → ไม่ต้องตั้งซ้ำ
        if abs(pos.tp - entry) < 0.5:
            continue

        # TF ของ order นั้น
        fvg_info = fvg_order_tickets.get(ticket)
        pos_tf_name = position_tf.get(ticket, "M1")
        if fvg_info:
            tf_val = TF_OPTIONS.get(fvg_info.get("tf","M1"), mt5.TIMEFRAME_M1)
        else:
            tf_val = TF_OPTIONS.get(pos_tf_name, mt5.TIMEFRAME_M1)

        rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, 10)
        if rates is None or len(rates) < 3:
            continue

        # แท่งล่าสุดและก่อนหน้า
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
            # ราคาลงต่ำกว่า entry
            tick = mt5.symbol_info_tick(SYMBOL)
            if not tick or tick.bid >= entry:
                continue
            if not bull_cur:  # แท่งปิดแดง
                # กลืนกิน: Close < Low[prev]
                if cur_c < prev_l:
                    trigger = True
                    reason  = f"แดงกลืนกิน Close:{cur_c:.2f} < Low[prev]:{prev_l:.2f}"
                # ตำหนิ: Low[cur] < Low[prev] และ Close ยังอยู่ใน range ของ prev
                elif cur_l < prev_l and prev_l <= cur_c <= prev_h:
                    trigger = True
                    reason  = f"แดงตำหนิ Low:{cur_l:.2f} < Low[prev]:{prev_l:.2f}"

        else:  # SELL
            tick = mt5.symbol_info_tick(SYMBOL)
            if not tick or tick.ask <= entry:
                continue
            if bull_cur:  # แท่งปิดเขียว
                # กลืนกิน: Close > High[prev]
                if cur_c > prev_h:
                    trigger = True
                    reason  = f"เขียวกลืนกิน Close:{cur_c:.2f} > High[prev]:{prev_h:.2f}"
                # ตำหนิ: High[cur] > High[prev] และ Close อยู่ใน range ของ prev
                elif cur_h > prev_h and prev_l <= cur_c <= prev_h:
                    trigger = True
                    reason  = f"เขียวตำหนิ High:{cur_h:.2f} > High[prev]:{prev_h:.2f}"

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
                        f"TP: `{pos.tp}` → `{entry}` (entry)\n"
                        f"เหตุผล: {reason}"
                    ))
                if _trade_debug_enabled():
                    print(f"🎯 [{now}] Breakeven {pos_type} {ticket}: TP→{entry} ({reason})")


async def _s6_process_ticket(app, pos, positions, state_dict, mode_tag, now,
                             _find_prev_swing_high, _find_prev_swing_low, strategy_1):
    """
    Core logic ท่า 6 — ใช้ร่วมทั้ง S6 เดิม (sid 2/3) และ S6 independent
    mode_tag: "S6" หรือ "S6i" สำหรับ log
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

    # ── ตรวจท่า 1 ทุก scan (ทั้ง wait และ count) ────────────
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
                                  f"TP: `{pos.tp}` → `{new_tp:.2f}`"))
                        if _trade_debug_enabled():
                            print(f"🎯 [{now}] {mode_tag} {ticket} TP→{new_tp:.2f} (ท่า1 {s1_signal})")
                else:
                    print(f"⚠️ [{now}] {mode_tag} skip invalid TP from S1 entry ticket={ticket} type={pos_type} entry={entry:.2f} new_tp={new_tp:.2f}")
        else:
            sell_positions = [p for p in positions
                              if p.type == mt5.ORDER_TYPE_SELL and p.ticket != ticket]
            if sell_positions or st.get("tp_set_by_s1"):
                ok, cp = _close_position(pos, pos_type, f"{mode_tag}: ท่า1 สวนทาง trigger")
                if ok:
                    state_dict.pop(ticket, None)
                    await tg(app, (f"🔒 *ปิด {pos_type} {mode_tag} — ท่า1 {s1_signal} trigger*\n"
                              f"{sig_e} Ticket:`{ticket}` [{tf_name}] ปิดที่`{cp:.2f}`"))
                    print(f"🔒 [{now}] {mode_tag} ปิด {pos_type} {ticket} ท่า1 trigger")
                return

    # ── init state ──────────────────────────────────────────
    if ticket not in state_dict:
        if pos_type == "BUY":
            sh_info = _find_prev_swing_high(rates)
            swing_ref = sh_info["price"] if sh_info else None
        else:
            sl_info = _find_prev_swing_low(rates)
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

    # แท่งล่าสุดที่ปิด
    cur_bar = rates[-1]
    cur_time = int(cur_bar["time"])
    cur_h  = float(cur_bar["high"])
    cur_l  = float(cur_bar["low"])
    cur_c  = float(cur_bar["close"])
    cur_o  = float(cur_bar["open"])
    bull   = cur_c > cur_o

    # ── Phase "wait": รอสัมผัส swing_h ─────────────────────
    if st["phase"] == "wait":
        touched = (pos_type == "BUY" and cur_h >= swing_h) or \
                  (pos_type == "SELL" and cur_l <= swing_h)
        if touched:
            st["phase"] = "count"
            st["count"] = 0
            st["last_bar_time"] = 0
            print(f"🎯 [{now}] {mode_tag} {ticket} สัมผัส swing={swing_h:.2f} เริ่มนับ")
        return

    # ── Phase "count": นับ 1-5 แท่ง ────────────────────────
    if cur_time == st["last_bar_time"]:
        return  # แท่งเดิม ไม่นับซ้ำ

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
                    await tg(app, (f"📐 *{mode_tag} Trail SL รอบ{st['trail_count']} — BUY*\n"
                              f"{sig_e} Ticket:`{ticket}` [{tf_name}]\n"
                              f"แท่งปิดเหนือ Swing:{swing_h:.2f}\n"
                              f"O:`{cur_o:.2f}` H:`{cur_h:.2f}` L:`{cur_l:.2f}` C:`{cur_c:.2f}`\n"
                              f"🛑 SL: `{pos.sl}` → `{new_sl}`"))
                    print(f"📐 [{now}] {mode_tag} Trail BUY {ticket}: {pos.sl}→{new_sl}")
            else:
                print(f"⚠️ [{now}] {mode_tag} Trail BUY {ticket}: new_sl={new_sl} ไม่ผ่าน (entry={entry} pos.sl={pos.sl})")
        else:
            new_sl = round(cur_h + 1.0, 2)
            if new_sl > entry and (pos.sl == 0 or new_sl < pos.sl):
                if _modify_sl(pos, new_sl):
                    st["trail_count"] += 1
                    await tg(app, (f"📐 *{mode_tag} Trail SL รอบ{st['trail_count']} — SELL*\n"
                              f"{sig_e} Ticket:`{ticket}` [{tf_name}]\n"
                              f"แท่งปิดใต้ Swing:{swing_h:.2f}\n"
                              f"O:`{cur_o:.2f}` H:`{cur_h:.2f}` L:`{cur_l:.2f}` C:`{cur_c:.2f}`\n"
                              f"🛑 SL: `{pos.sl}` → `{new_sl}`"))
                    print(f"📐 [{now}] {mode_tag} Trail SELL {ticket}: {pos.sl}→{new_sl}")
            else:
                print(f"⚠️ [{now}] {mode_tag} Trail SELL {ticket}: new_sl={new_sl} ไม่ผ่าน (entry={entry} pos.sl={pos.sl})")

        # หา swing ใหม่จากแท่งที่ปิดเหนือ → reset
        if pos_type == "BUY":
            sh_info = _find_prev_swing_high(rates)
            new_swing = sh_info["price"] if sh_info and sh_info["price"] > swing_h else None
        else:
            sl_info = _find_prev_swing_low(rates)
            new_swing = sl_info["price"] if sl_info and sl_info["price"] < swing_h else None

        if new_swing:
            st["swing_h"] = new_swing
            st["phase"]   = "wait"
            st["count"]   = 0
            print(f"🔄 [{now}] {mode_tag} {ticket} swing ใหม่={new_swing:.2f} รอสัมผัส")
        else:
            state_dict.pop(ticket, None)
            print(f"✅ [{now}] {mode_tag} {ticket} ไม่มี swing ใหม่ จบ")

    elif st["count"] >= 5:
        # ครบ 5 แท่ง ไม่ผ่าน → ตั้ง TP = entry
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
                      f"TP → `{entry}`"))
            print(f"🎯 [{now}] {mode_tag} {ticket} TP=entry={entry}")


# ── S6i helpers: ตรวจ S1/S3 pattern (ไม่สนใจ zone) ────────────

def _has_s1_sell_pattern(rates):
    """S1 SELL pattern (ไม่สนใจ zone): green[2]→red[1]→red[0] close<low[1]"""
    if len(rates) < 4:
        return False
    o0, h0, l0, c0 = [float(rates[-1][k]) for k in ('open','high','low','close')]
    o1, h1, l1, c1 = [float(rates[-2][k]) for k in ('open','high','low','close')]
    o2, h2, l2, c2 = [float(rates[-3][k]) for k in ('open','high','low','close')]
    bull0, bull1, bull2 = c0 > o0, c1 > o1, c2 > o2
    return bull2 and not bull1 and not bull0 and c0 < l1


def _has_s1_buy_pattern(rates):
    """S1 BUY pattern (ไม่สนใจ zone): red[2]→green[1]→green[0] close>high[1]"""
    if len(rates) < 4:
        return False
    o0, h0, l0, c0 = [float(rates[-1][k]) for k in ('open','high','low','close')]
    o1, h1, l1, c1 = [float(rates[-2][k]) for k in ('open','high','low','close')]
    o2, h2, l2, c2 = [float(rates[-3][k]) for k in ('open','high','low','close')]
    bull0, bull1, bull2 = c0 > o0, c1 > o1, c2 > o2
    return not bull2 and bull1 and bull0 and c0 > h1


def _has_s3_sell_pattern(rates):
    """S3 SP SELL pattern (ไม่สนใจ zone): red[2] body≥35% → green/doji[1] → red[0] close<low[1]"""
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
    """S3 SP BUY pattern (ไม่สนใจ zone): green[2] body≥35% → red/doji[1] → green[0] close>high[1]"""
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
    """ตรวจว่ามี pending order ฝั่ง side ใกล้ราคา price ไหม"""
    orders = mt5.orders_get(symbol=SYMBOL)
    if not orders:
        return False
    otype = mt5.ORDER_TYPE_SELL_LIMIT if side == "SELL" else mt5.ORDER_TYPE_BUY_LIMIT
    return any(o.type == otype and abs(o.price_open - price) <= tolerance for o in orders)


# ── S6i: state machine ท่า 6 อิสระ ──────────────────────────

async def _s6i_process_ticket(app, pos, now,
                              _find_prev_swing_high, _find_prev_swing_low):
    """
    S6i — 2 High 2 Low Independent
    Phase: watch → count → wait_swing2 → order_placed

    SELL: หา swing HIGH (resistance) → ตรวจ pattern → ตั้ง TP/order
    BUY:  หา swing LOW  (support)   → สลับฝั่ง
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

    # ── side-dependent references ────────────────────────────
    find_swing    = _find_prev_swing_low  if is_buy else _find_prev_swing_high
    find_swing_tp = _find_prev_swing_high if is_buy else _find_prev_swing_low
    has_s1        = _has_s1_buy_pattern   if is_buy else _has_s1_sell_pattern
    has_s3        = _has_s3_buy_pattern   if is_buy else _has_s3_sell_pattern
    order_side    = "BUY" if is_buy else "SELL"
    opp_lim_type  = mt5.ORDER_TYPE_SELL_LIMIT if is_buy else mt5.ORDER_TYPE_BUY_LIMIT
    our_lim_type  = mt5.ORDER_TYPE_BUY_LIMIT  if is_buy else mt5.ORDER_TYPE_SELL_LIMIT

    # ── Init: find swing, check S1/S3 pattern, set TP ────────
    if ticket not in _s6i_state:
        sw_info   = find_swing(rates)
        swing_ref = sw_info["price"] if sw_info else None
        if not swing_ref:
            return

        s1_found = (has_s1(rates) or has_s3(rates) or
                    _has_opposite_order_near(order_side, swing_ref))

        tp_source = None
        if not s1_found:
            # TP = entry ของ opposite limit (ท่า 2/3) หรือ swing TP
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
                    await tg(app, (f"🎯 *S6i ตั้ง TP — {pos_type}*\n"
                              f"{sig_e} Ticket:`{ticket}` [{tf_name}]\n"
                              f"TP: `{pos.tp}` → `{opp_entry:.2f}`"))
                    if _trade_debug_enabled():
                        print(f"🎯 [{now}] S6i {ticket} TP→{opp_entry:.2f}")
            elif opp_entry and not _tp_valid_for_side(pos_type, pos.price_open, round(opp_entry, 2), 0.01):
                print(f"⚠️ [{now}] S6i skip invalid TP ticket={ticket} type={pos_type} entry={pos.price_open:.2f} new_tp={opp_entry:.2f}")

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

    # ── Monitor: opposite limit fill → ปิด position ──────────
    if st.get("tp_source"):
        pending = mt5.orders_get(symbol=SYMBOL)
        still_exists = pending and any(o.ticket == st["tp_source"] for o in pending)
        if not still_exists:
            ok, cp = _close_position(pos, pos_type, "S6i: opposite limit filled")
            if ok:
                _s6i_state.pop(ticket, None)
                await tg(app, (f"🔒 *ปิด {pos_type} S6i — ฝั่งตรงข้าม fill*\n"
                          f"{sig_e} Ticket:`{ticket}` [{tf_name}] ปิดที่`{cp:.2f}`"))
                print(f"🔒 [{now}] S6i ปิด {pos_type} {ticket} opposite fill")
            return

    # ── Current bar ──────────────────────────────────────────
    cur_bar  = rates[-1]
    cur_time = int(cur_bar["time"])
    cur_c    = float(cur_bar["close"])
    cur_o    = float(cur_bar["open"])
    cur_h    = float(cur_bar["high"])
    cur_l    = float(cur_bar["low"])
    bull     = cur_c > cur_o

    # ════════════════════════════════════════════════════════
    #  Phase: watch — รอดูว่าแท่งปิดผ่าน swing ได้ไหม
    # ════════════════════════════════════════════════════════
    if st["phase"] == "watch":
        if cur_time == st["last_bar_time"]:
            return
        st["last_bar_time"] = cur_time

        # SELL: เขียว close > swing_h1 → ผ่าน → หา swing ใหม่
        # BUY:  แดง  close < swing_l1 → ผ่าน → หา swing ใหม่
        broke_out     = (bull and cur_c > swing1) if not is_buy else (not bull and cur_c < swing1)
        # SELL: เขียว close ≤ swing_h1 → เข้า count
        # BUY:  แดง  close ≥ swing_l1 → เข้า count
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
                    # อัพเดต TP
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
                                print(f"🎯 [{now}] S6i {ticket} TP→{opp_entry:.2f} (swing ใหม่)")
                    elif opp_entry and not _tp_valid_for_side(pos_type, pos.price_open, round(opp_entry, 2), 0.01):
                        print(f"⚠️ [{now}] S6i skip invalid TP at new swing ticket={ticket} type={pos_type} entry={pos.price_open:.2f} new_tp={opp_entry:.2f}")

                print(f"🔄 [{now}] S6i {ticket} new swing={new_sw:.2f} s1={s1_found}")
            return

        if trigger_count:
            st["phase"] = "count"
            st["count"] = 1
            print(f"📊 [{now}] S6i {ticket} watch→count")
            return

    # ════════════════════════════════════════════════════════
    #  Phase: count — นับ 1-5 แท่ง
    # ════════════════════════════════════════════════════════
    elif st["phase"] == "count":
        if cur_time == st["last_bar_time"]:
            return
        st["last_bar_time"] = cur_time
        st["count"] += 1

        prev_h = float(rates[-2]["high"])
        prev_l = float(rates[-2]["low"])

        # SELL: เขียว close > swing_h1 AND > prev_high → ผ่าน → restart
        # BUY:  แดง  close < swing_l1 AND < prev_low  → ผ่าน → restart
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
                print(f"🔄 [{now}] S6i {ticket} count→watch new swing={new_sw:.2f}")
            return

        # ครบ 5 แท่ง → หา swing2
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
                print(f"⏳ [{now}] S6i {ticket} ครบ 5 แท่ง ไม่มี swing2 → รอ")

    # ════════════════════════════════════════════════════════
    #  Phase: wait_swing2 — รอ swing ที่ 2
    # ════════════════════════════════════════════════════════
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

    # ════════════════════════════════════════════════════════
    #  Phase: order_placed — monitor SELL/BUY limit ที่ตั้ง
    # ════════════════════════════════════════════════════════
    elif st["phase"] == "order_placed":
        order_ticket = st.get("order_ticket")
        swing2       = st.get("swing_h2")
        if not order_ticket:
            _s6i_state.pop(ticket, None)
            return

        # order ยังอยู่ไหม
        orders = mt5.orders_get(symbol=SYMBOL)
        order_exists = orders and any(o.ticket == order_ticket for o in orders)
        if not order_exists:
            _s6i_state.pop(ticket, None)
            print(f"✅ [{now}] S6i {ticket} order {order_ticket} filled/cancelled → done")
            return

        # กลืนกิน swing2 → ยกเลิก order
        if swing2:
            cancel = (bull and cur_c > swing2) if not is_buy else (not bull and cur_c < swing2)
            if cancel:
                r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": order_ticket})
                if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                    _s6i_state.pop(ticket, None)
                    await tg(app, (f"❌ *S6i ยกเลิก — กลืนกิน swing2*\n"
                              f"🔖 Order:`{order_ticket}` ยกเลิก"))
                    print(f"❌ [{now}] S6i cancel {order_ticket} engulf swing2")


async def _s6i_on_swing2(app, pos, pos_type, rates, st, swing1, swing2,
                         now, sig_e, tf_name, ticket, is_buy,
                         has_s1, has_s3, order_side, our_lim_type,
                         find_swing_tp):
    """เจอ swing ที่ 2 → ตรวจ S1/S3 pattern → ตั้ง order หรือรอ"""
    st["swing_h2"] = swing2
    s1_at_2 = (has_s1(rates) or has_s3(rates) or
               _has_opposite_order_near(order_side, swing2))

    if s1_at_2:
        # S1/S3 เจอที่ swing2 → รอ limit ปกติ, set TP ตาม opposite limit
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
                    print(f"🎯 [{now}] S6i {ticket} TP→{opp_entry:.2f} (S1/S3 at swing2)")
        elif opp_entry and not _tp_valid_for_side(pos_type, pos.price_open, round(opp_entry, 2), 0.01):
            print(f"⚠️ [{now}] S6i skip invalid TP at swing2 ticket={ticket} type={pos_type} entry={pos.price_open:.2f} new_tp={opp_entry:.2f}")

        st["phase"] = "watch"
        st["swing_h1"] = swing2
        st["count"] = 0
        print(f"✅ [{now}] S6i {ticket} swing2={swing2:.2f} S1/S3 found → watch ต่อ")
    else:
        # ไม่เจอ S1/S3 → ตั้ง limit order ที่ swing1
        sw_tp_info = find_swing_tp(rates)
        tp_price   = sw_tp_info["price"] if sw_tp_info else None
        if not tp_price:
            print(f"⚠️ [{now}] S6i {ticket} ไม่เจอ swing TP → ข้าม")
            _s6i_state.pop(ticket, None)
            return

        # SELL: SL = swing_h2 + 100pt | BUY: SL = swing_l2 − 100pt
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
                      f"🔖 Order:`{r.order}`"))
            print(f"📌 [{now}] S6i {side_label} LIMIT at {swing1:.2f} SL={sl_price} TP={tp_price}")
        else:
            retcode = r.retcode if r else "None"
            print(f"❌ [{now}] S6i order FAIL retcode={retcode}")
            _s6i_state.pop(ticket, None)


async def check_s6_trail(app):
    """
    ท่าที่ 6 — 2 High 2 Low Trail SL
    - S6 เดิม: ต่อเนื่องจาก position ท่า 2/3
    - S6i: scan swing + ตั้ง order ใหม่ (ทุก position ที่ entry done)
    ทั้งสองทำงานพร้อมกัน
    """
    from strategy4 import _find_prev_swing_high, _find_prev_swing_low
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

        # S6 เดิม: เฉพาะ sid 2/3
        if s6_on and sid in (2, 3):
            if _trade_debug_enabled():
                print(f"[{now}] 🔍 S6: {pos_type} {ticket} sid={sid}")
            await _s6_process_ticket(app, pos, positions, _s6_state, "S6", now,
                                     _find_prev_swing_high, _find_prev_swing_low, strategy_1)

        # S6i: ทุก position ที่ S6 เดิมไม่ได้ track → scan swing + ตั้ง order
        if s6i_on and ticket not in _s6_state:
            if _trade_debug_enabled():
                print(f"[{now}] 🔍 S6i: {pos_type} {ticket} sid={sid}")
            await _s6i_process_ticket(app, pos, now,
                                      _find_prev_swing_high, _find_prev_swing_low)


async def check_cancel_pending_orders(app):
    """
    Auto cancel limit orders เมื่อ setup ไม่ valid:
    BUY LIMIT:  ราคาปิดเหนือ Swing High หลักของ TF นั้น → ลบออก
    SELL LIMIT: ราคาปิดต่ำกว่า Swing Low หลักของ TF นั้น → ลบออก

    Swing High/Low หลัก = max/min ของ lookback ทั้งหมดของ TF นั้น
    """
    orders = mt5.orders_get(symbol=SYMBOL)
    if not orders:
        pending_order_tf.clear()
        return

    now = now_bkk().strftime("%H:%M:%S")
    open_tickets = {o.ticket for o in orders}

    # cleanup tickets ที่ไม่มีแล้ว
    for t in list(pending_order_tf.keys()):
        if t not in open_tickets:
            pending_order_tf.pop(t, None)

    for order in orders:
        ticket = order.ticket
        info   = pending_order_tf.get(ticket)
        if not info:
            continue
        tf = info.get("tf") if isinstance(info, dict) else info

        # ใช้ TF เล็กสุด (check_tf) สำหรับตรวจแท่ง candle quality
        # ใช้ tf หลักสำหรับ Swing H/L
        check_tf = position_tf.get(ticket) or tf

        tf_val   = TF_OPTIONS.get(tf, mt5.TIMEFRAME_M1)
        lookback = TF_LOOKBACK.get(tf, SWING_LOOKBACK)
        rates    = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, lookback + 6)
        if rates is None or len(rates) < 5:
            continue

        # Swing High/Low หลัก = max/min ของ lookback ทั้งหมด (ใช้ tf หลัก)
        swing_high = max(float(r["high"]) for r in rates)
        swing_low  = min(float(r["low"])  for r in rates)

        last_close = float(rates[-1]["close"])

        # rates สำหรับ candle quality ใช้ check_tf (TF เล็กสุด)
        check_tf_val   = TF_OPTIONS.get(check_tf, mt5.TIMEFRAME_M1)
        check_lookback = min(TF_LOOKBACK.get(check_tf, SWING_LOOKBACK) + 6, 50)
        candle_rates   = mt5.copy_rates_from_pos(SYMBOL, check_tf_val, 1, check_lookback)
        if candle_rates is None:
            candle_rates = rates

        should_cancel = False
        reason = ""

        # ── Limit TP/SL Break Cancel: ยกเลิกเมื่อแท่งยืนยันทะลุ TP/SL ตาม TF ที่เลือก ──
        # ข้าม S2 pattern 1 (เขียวกลืนกิน/แดงกลืนกิน) ตามกติกา
        _skip_break = (
            isinstance(info, dict)
            and info.get("sid") == 2
            and info.get("c3_type") in ("เขียวกลืนกิน", "แดงกลืนกิน")
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
                        f"TP Break Cancel [{tf}]: BUY LIMIT ถูกแท่งเขียวยืนยันเหนือ TP "
                        f"close:{_bar_close(cur_bar):.2f} > TP:{limit_tp:.2f} "
                        f"& engulf High[prev]:{_bar_high(prev_bar):.2f}"
                    )
                elif limit_sl > 0 and _is_red_engulf_break(cur_bar, prev_bar, limit_sl):
                    should_cancel = True
                    reason = (
                        f"SL Break Cancel [{tf}]: BUY LIMIT ถูกแท่งแดงยืนยันใต้ SL "
                        f"close:{_bar_close(cur_bar):.2f} < SL:{limit_sl:.2f} "
                        f"& engulf Low[prev]:{_bar_low(prev_bar):.2f}"
                    )

            elif order.type == mt5.ORDER_TYPE_SELL_LIMIT:
                if limit_tp > 0 and _is_red_engulf_break(cur_bar, prev_bar, limit_tp):
                    should_cancel = True
                    reason = (
                        f"TP Break Cancel [{tf}]: SELL LIMIT ถูกแท่งแดงยืนยันใต้ TP "
                        f"close:{_bar_close(cur_bar):.2f} < TP:{limit_tp:.2f} "
                        f"& engulf Low[prev]:{_bar_low(prev_bar):.2f}"
                    )
                elif limit_sl > 0 and _is_green_engulf_break(cur_bar, prev_bar, limit_sl):
                    should_cancel = True
                    reason = (
                        f"SL Break Cancel [{tf}]: SELL LIMIT ถูกแท่งเขียวยืนยันเหนือ SL "
                        f"close:{_bar_close(cur_bar):.2f} > SL:{limit_sl:.2f} "
                        f"& engulf High[prev]:{_bar_high(prev_bar):.2f}"
                    )

        # ── Limit Guard: ยกเลิก limit ที่ entry ไกลจาก position ที่เปิดอยู่ ──
        if not should_cancel and config.LIMIT_GUARD:
            limit_tf = info.get("tf") if isinstance(info, dict) else info
            positions = mt5.positions_get(symbol=SYMBOL)
            tf_separate = config.LIMIT_GUARD_TF_MODE == "separate"
            if positions and (limit_tf or not tf_separate):
                sym_info = mt5.symbol_info(SYMBOL)
                pt = sym_info.point if sym_info else 0.01
                guard_dist = config.LIMIT_GUARD_POINTS * pt * config.points_scale()  # BTC = 4× (background)

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
                            reason = (f"Limit Guard [{limit_tf}→{matched_tf}]: BUY LIMIT {limit_entry:.2f} > "
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
                            reason = (f"Limit Guard [{limit_tf}→{matched_tf}]: SELL LIMIT {limit_entry:.2f} < "
                                      f"SELL pos {pos_entry:.2f} "
                                      f"& ask {ask:.2f} < {pos_entry - guard_dist:.2f} (-{config.LIMIT_GUARD_POINTS}pt)")
                            break

        # ── Limit Trend Recheck: เช็ค trend ก่อน fill เมื่อราคาใกล้ entry ──
        _order_sid = info.get("sid") if isinstance(info, dict) else None
        if not should_cancel and config.LIMIT_TREND_RECHECK and _order_sid not in (1, 9, 10, 11):
            _tick = mt5.symbol_info_tick(SYMBOL)
            _sym  = mt5.symbol_info(SYMBOL)
            if _tick and _sym:
                _pt           = _sym.point or 0.01
                _recheck_dist = config.LIMIT_TREND_RECHECK_POINTS * _pt * config.points_scale()
                _limit_entry  = order.price_open
                if order.type == mt5.ORDER_TYPE_BUY_LIMIT:
                    _cur_price    = _tick.ask
                    _order_signal = "BUY"
                else:
                    _cur_price    = _tick.bid
                    _order_signal = "SELL"
                if abs(_cur_price - _limit_entry) <= _recheck_dist:
                    from scanner import trend_allows_signal as _tas
                    _allowed, _why = _tas(tf, _order_signal)
                    if not _allowed:
                        should_cancel = True
                        _dist_pt = round(abs(_cur_price - _limit_entry) / _pt)
                        reason = (
                            f"Trend Recheck Cancel [{tf}]: {_order_signal} LIMIT entry:{_limit_entry:.2f} "
                            f"ใกล้ {_dist_pt}pt แต่ trend={_why}"
                        )

        # ── Near Approach Cancel: ยกเลิก limit เมื่อราคาเข้าใกล้แล้วกลับตัว ──
        if not should_cancel and config.NEAR_APPROACH_CANCEL_ENABLED:
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
                                f"high ขึ้นมาใกล้ {_dist_pt}pt แล้วกลับตัว"
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
                                f"low ลงมาใกล้ {_dist_pt}pt แล้วกลับตัว"
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
                    # S8 original: รอ breakout ผ่าน Swing
                    swing_price = float(info.get("swing_price", 0) or 0)
                    swing_bar_time = int(info.get("swing_bar_time", 0) or 0)
                    latest_bar = rates[-1] if len(rates) > 0 else None
                    if swing_price > 0 and latest_bar is not None and int(latest_bar["time"]) > swing_bar_time:
                        if sig == "SELL" and float(latest_bar["high"]) > swing_price:
                            arm_now = True
                            arm_reason = "breakout เหนือ Swing High"
                        elif sig == "BUY" and float(latest_bar["low"]) < swing_price:
                            arm_now = True
                            arm_reason = "breakout ใต้ Swing Low"

                elif config.DELAY_SL_MODE == "time":
                    # ตั้ง SL ใน 10% สุดท้ายของ TF
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
                            arm_reason = f"เหลือ {_time_left}s < {_threshold:.0f}s (10% ของ {tf})"

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
                            f"🛡  *ตั้ง SL {ot}*\n"
                            f"{sig_e} [{tf}] Ticket:`{ticket}`\n"
                            f"🛑 SL: `{intended_sl:.2f}`\n"
                            f"เหตุผล: {arm_reason}"
                        ))
                        print(f"🛡  [{now}] arm SL {ot} {ticket}: SL={intended_sl:.2f} ({arm_reason})")
                    else:
                        info["sl_arm_retry_count"] = int(info.get("sl_arm_retry_count", 0) or 0) + 1
                        pending_order_tf[ticket] = info
                        save_runtime_state()
                        retcode = getattr(r_mod, "retcode", None) if r_mod is not None else None
                        comment = getattr(r_mod, "comment", "") if r_mod is not None else ""
                        print(
                            f"⚠️ [{now}] arm SL retry {ticket}: "
                            f"attempt={info['sl_arm_retry_count']} SL={intended_sl:.2f} "
                            f"retcode={retcode} comment={comment}"
                        )

        # Reverse limit: ถ้าหลังแท่ง detect ปิดไปแล้ว 3 แท่งและยังไม่ fill -> ยกเลิก
        if isinstance(info, dict) and info.get("reverse"):
            detect_time = int(info.get("detect_bar_time", 0) or 0)
            if detect_time:
                bars_after_detect = [r for r in candle_rates if int(r["time"]) > detect_time]
                if len(bars_after_detect) >= 3:
                    should_cancel = True
                    reason = f"Reverse limit หมดอายุหลัง {check_tf} ปิดไปแล้ว 3 แท่งนับจาก detect bar"

        # S8 Swing Limit: ยกเลิกเมื่อ swing เปลี่ยน
        if not should_cancel and isinstance(info, dict) and info.get("swing_price") and info.get("sid") == 8:
            from strategy4 import _find_prev_swing_high, _find_prev_swing_low
            old_swing = info["swing_price"]
            sig = info.get("signal", "")
            if sig == "SELL":
                new_sh = _find_prev_swing_high(rates)
                if new_sh and abs(new_sh["price"] - old_swing) > 0.01:
                    should_cancel = True
                    reason = f"Swing High เปลี่ยน {old_swing:.2f} → {new_sh['price']:.2f}"
            elif sig == "BUY":
                new_sl = _find_prev_swing_low(rates)
                if new_sl and abs(new_sl["price"] - old_swing) > 0.01:
                    should_cancel = True
                    reason = f"Swing Low เปลี่ยน {old_swing:.2f} → {new_sl['price']:.2f}"

        # cancel_bars: ยกเลิกหลัง N แท่ง (เช่น Pattern E ยกเลิกหลัง 1 แท่ง)
        if not should_cancel and isinstance(info, dict) and info.get("cancel_bars"):
            detect_time = int(info.get("detect_bar_time", 0) or 0)
            if detect_time:
                bars_after = [r for r in candle_rates if int(r["time"]) > detect_time]
                if len(bars_after) >= info["cancel_bars"]:
                    should_cancel = True
                    reason = f"หมดอายุหลัง {info['cancel_bars']} แท่ง ({check_tf})"

        if order.type == mt5.ORDER_TYPE_BUY_LIMIT:
            # BUY LIMIT: ลบเมื่อราคาปิดเหนือ Swing High หลัก
            if not should_cancel and last_close > swing_high:
                should_cancel = True
                reason = f"Close:{last_close:.2f} > Swing High:{swing_high:.2f}"
            # BUY LIMIT: แท่งถัดจาก detect ปิดแดง body≥35% → setup ล้มเหลว
            elif not should_cancel:
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
                            reason = (f"แท่งถัดไป{check_tf}แดง body:{body*100:.0f}%"
                                      f" O:{o_:.2f} H:{float(nb['high']):.2f}"
                                      f" L:{float(nb['low']):.2f} C:{c_:.2f}"
                                      f" setup ล้มเหลว")

        elif order.type == mt5.ORDER_TYPE_SELL_LIMIT:
            # SELL LIMIT: ลบเมื่อราคาปิดต่ำกว่า Swing Low หลัก
            if not should_cancel and last_close < swing_low:
                should_cancel = True
                reason = f"Close:{last_close:.2f} < Swing Low:{swing_low:.2f}"
            # SELL LIMIT: แท่งถัดจาก detect ปิดเขียว body≥35% → setup ล้มเหลว
            elif not should_cancel:
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

        if should_cancel:
            r = mt5.order_send({
                "action": mt5.TRADE_ACTION_REMOVE,
                "order":  ticket,
            })
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                pending_order_tf.pop(ticket, None)
                sig_e = "🟢" if order.type == mt5.ORDER_TYPE_BUY_LIMIT else "🔴"
                ot    = "BUY LIMIT" if order.type == mt5.ORDER_TYPE_BUY_LIMIT else "SELL LIMIT"
                log_event(
                    "ORDER_CANCELED",
                    reason,
                    ticket=ticket,
                    tf=tf,
                    side="BUY" if order.type == mt5.ORDER_TYPE_BUY_LIMIT else "SELL",
                    order_type=ot,
                    entry=order.price_open,
                )
                await tg(app, (
                        f"🗑  *ยกเลิก {ot} อัตโนมัติ*\n"
                        f"{sig_e} [{tf}] Ticket:`{ticket}`\n"
                        f"Entry:`{order.price_open}`\n"
                        f"เหตุผล: {reason}"
                    ))
                print(f"🗑  [{now}] ยกเลิก {ot} {ticket} [{tf}]: {reason}")


# ─────────────────────────────────────────────────────────────
async def check_limit_sweep(app):
    """
    Limit Sweep — เมื่อ position จบแท่งสวนทาง + ราคาทะลุ prev low/high
    BUY:  แท่งจบแดง + close < prev low → ปิด position + sweep BUY LIMITs ใน TF
          → เหลือตัวใกล้ Swing LL ที่สุด / ถ้าไม่มี → ตั้ง S8 ที่ LL
    SELL: แท่งจบเขียว + close > prev high → ปิด position + sweep SELL LIMITs ใน TF
          → เหลือตัวใกล้ Swing HH ที่สุด / ถ้าไม่มี → ตั้ง S8 ที่ HH
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

        # ── 1) ปิด position ──
        comment = f"Sweep_{tf}"
        ok, close_price = _close_position(pos, pos_type, comment)
        if not ok:
            print(f"[{now}] ⚠️ Limit Sweep: ปิด {pos_type} #{ticket} ไม่สำเร็จ")
            continue

        reason_detail = (f"แท่งจบ{'แดง' if is_red else 'เขียว'} close={bar_close:.2f} "
                         f"{'< prev low' if pos_type == 'BUY' else '> prev high'}="
                         f"{prev_low if pos_type == 'BUY' else prev_high:.2f}")
        print(f"[{now}] 🧹 Limit Sweep: ปิด {pos_type} #{ticket} [{tf}] {reason_detail}")

        # ── 2) หา Swing LL (BUY) หรือ HH (SELL) ──
        sh_info = _find_prev_swing_high(rates)
        sl_info = _find_prev_swing_low(rates)

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

        # ── 3) หา limit orders ใน TF เดียวกัน ──
        #   ในช่วง LL–H / L–HH → ยกเลิกทุกท่า
        #   นอกช่วง → ยกเลิกเฉพาะท่าที่ 8
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

        # ── 4) เหลือตัวใกล้ LL/HH ที่สุด ยกเลิกที่เหลือในช่วง ──
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
            rng = f"{'LL' if pos_type == 'BUY' else 'L'}–{'H' if pos_type == 'BUY' else 'HH'}"
            print(f"[{now}] 🧹 Sweep keep #{kept_ticket} [{tf}] ใกล้ {'LL' if pos_type == 'BUY' else 'HH'}={target_price:.2f} (range {rng})")

        # ── 5) ถ้าไม่มี limit ใกล้ target → ตั้ง S8 ──
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
                    print(f"[{now}] 🧹 Sweep → S8 {s8_signal} LIMIT #{s8_ticket} [{tf}] "
                          f"Entry={s8_entry:.2f} SL={s8_sl:.2f} TP={s8_tp:.2f} "
                          f"{'LL' if pos_type == 'BUY' else 'HH'}={target_price:.2f}")
                    await tg(app,
                        f"🧹 *Limit Sweep → S8*\n"
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
        config.save_runtime_state()


async def check_fvg_candle_quality(app):
    """Deprecated — ท่าที่ 2 ใช้ check_entry_candle_quality เหมือนทุกท่าแล้ว"""
    pass


# ─────────────────────────────────────────────────────────────
async def _s12_close_all(app, reason: str):
    """ปิด S12 positions ทั้งหมด — ใช้ใน flip + breakout"""
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
    # side ไม่ล้างที่นี่ — caller กำหนดเอง

    now_str = now_bkk().strftime("%H:%M:%S")
    profit_str = f"+{total_profit:.2f}" if total_profit >= 0 else f"{total_profit:.2f}"
    print(f"🗑 [{now_str}] S12 ปิด {closed} positions profit={profit_str}: {reason}")
    await tg(app, (
        f"🗑 *S12 ปิด {closed} position*\n"
        f"Profit: `{profit_str}`\n"
        f"เหตุผล: {reason}"
    ))


async def check_s12_management(app):
    """S12 Range Trading management — ตรวจ flip + breakout"""
    from strategy12 import _s12_state, s12_get_swing, s12_cleanup_tickets

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

    swing_high, swing_low = s12_get_swing(rates_m5, config.S12_LOOKBACK)

    # ── ตรวจ Breakout (แท่งปิดล่าสุด) ──
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

    # ── ตรวจ Flip ──
    bid = float(tick.bid)
    ask = float(tick.ask)

    if side == "SELL" and ask <= swing_low + zone_dist:
        await _s12_close_all(app, f"Flip → BUY: ราคาถึง bottom zone {swing_low:.2f}")
        _s12_state["side"]             = "BUY"
        _s12_state["order_count"]      = 0
        _s12_state["last_entry_price"] = None
    elif side == "BUY" and bid >= swing_high - zone_dist:
        await _s12_close_all(app, f"Flip → SELL: ราคาถึง top zone {swing_high:.2f}")
        _s12_state["side"]             = "SELL"
        _s12_state["order_count"]      = 0
        _s12_state["last_entry_price"] = None
