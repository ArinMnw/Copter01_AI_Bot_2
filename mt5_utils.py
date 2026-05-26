import re
import config
from config import *


def _scale_out_resolve_volume(base_volume: float, sid="", direction: str = "",
                              entry: float = 0.0, tp: float = 0.0) -> tuple:
    """
    คำนวณ TSO scaled volume — เสมอ base × 4 (เมื่อ TP valid)
    Return: (scaled_volume, effective_steps_list)
      - effective_steps_list = 4 step distances (หน่วยราคา) — empty ถ้าไม่ scale

    Logic:
      - skip S13 (มี logic แยก — สร้าง 4 orders แยก)
      - skip ถ้า TSO disabled หรือ TP/entry invalid
      - คำนวณ effective_steps (เสมอ 4 steps) จาก config.compute_tso_effective_steps
      - scaled_volume = 4 × base_volume
    """
    try:
        if str(sid) == "13":
            return float(base_volume), []
        if not config.SCALE_OUT_ENABLED or base_volume <= 0:
            return float(base_volume), []
        if entry <= 0 or tp <= 0 or direction not in ("BUY", "SELL"):
            return float(base_volume), []
        # คำนวณ tp_orig_dist (price units, positive)
        if direction == "BUY":
            tp_orig_dist = tp - entry
        else:
            tp_orig_dist = entry - tp
        if tp_orig_dist <= 0:
            return float(base_volume), []
        effective_steps = config.compute_tso_effective_steps(tp_orig_dist, sid=sid)
        if not effective_steps:
            return float(base_volume), []
        scaled = round(float(base_volume) * len(effective_steps), 2)
        return scaled, effective_steps
    except Exception:
        return float(base_volume), []


def _scale_out_register_ticket(ticket: int, direction: str, entry: float,
                               base_volume: float, scaled_volume: float,
                               sid="", tp_original: float = 0.0,
                               effective_steps: list = None):
    """
    ลงทะเบียน ticket TSO ลง config.scale_out_state
    effective_steps = list ของ step distances (หน่วยราคา) ที่คำนวณตาม TP เดิม
    """
    try:
        if not ticket or ticket <= 0:
            return
        per_tp = float(base_volume)   # ปิดทีละ base_volume ต่อ step (ไม่ใช่ scale_out_per_tp_volume เดิม)
        tp_distances = list(effective_steps or [])
        # fallback: ถ้าไม่ได้ส่ง effective_steps มา ให้ใช้ tp_distances default (legacy)
        if not tp_distances:
            tp_distances = list(config.scale_out_tp_distances())
        n_steps = len(tp_distances)
        config.scale_out_state[int(ticket)] = {
            "direction":       direction,
            "entry":           float(entry),
            "original_volume": float(scaled_volume),
            "base_volume":     float(base_volume),       # lot เดิมก่อน scale (ไว้ revert ตอน OFF)
            "per_tp_volume":   float(per_tp),
            "tp_distances":   list(tp_distances),
            "step":           0,                          # ปิดไปแล้วกี่ขั้น
            "is_pending":     True,                       # True = ยังไม่ fill
            "sid":            str(sid) if sid else "",    # ใช้สำหรับ S10 special rule
            "tp_original":    float(tp_original or 0.0), # TP เดิมจาก order
        }
        # ── log event เพื่อให้พี่ชายเห็นใน bot.log ว่า ticket ไหนเป็น TSO ──
        try:
            from bot_log import log_event
            steps_str = ",".join(f"{d:.2f}" for d in tp_distances)
            log_event(
                "TSO_REGISTERED",
                f"TSO ON ×{n_steps} | base={base_volume} → scaled={scaled_volume} | "
                f"per_tp={per_tp} | effective steps (price)=[{steps_str}]",
                ticket=int(ticket),
                side=direction,
                sid=sid,
                entry=float(entry),
                scaled_volume=float(scaled_volume),
                base_volume=float(base_volume),
                tp_original=float(tp_original or 0.0),
                n_steps=n_steps,
            )
        except Exception:
            pass
    except Exception as e:
        try:
            from datetime import datetime
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ TSO register error: {e}")
        except Exception:
            pass


def _pattern_comment_code(pattern: str, sid="") -> str:
    text = (pattern or "").upper()
    raw = pattern or ""
    sid_text = str(sid or "")

    if sid_text == "1":
        # ตรวจ suffix หลัง "— Pattern ..." เพื่อไม่ให้ prefix "กลืนกิน/ตำหนิ/ย้อนโครงสร้าง" รบกวน
        if "กลืนกิน 2 แดง" in raw or "กลืนกิน 2 เขียว" in raw:
            return "P5"
        if "Pattern ใหม่ 4" in raw or "4 แท่ง" in raw:
            return "P4"
        if "Pattern F" in raw or "2 แท่งกลืนกิน" in raw:
            return "P6"
        if "Pattern ย้อนโครงสร้าง" in raw:
            return "P3"
        if "Pattern ตำหนิ" in raw:
            return "P2"
        if "Pattern กลืนกิน" in raw:
            return "P1"

    if sid_text == "2":
        if "ปฏิเสธราคา" in raw:
            return "P2"
        if "เขียวกลืนกิน" in raw or "แดงกลืนกิน" in raw:
            return "P1"

    if sid_text == "3":
        if "DM SP" in text:
            m = re.search(r'\[C1:([A-Z_]+)\]', raw)
            if m:
                return m.group(1)
            return "DMSP"

    if sid_text == "13":
        if "EZALGO" in text:
            return "EZ"

    if sid_text == "14":
        is_buy  = "BUY"  in text
        is_engulf = "ENGULF" in text
        if is_buy:
            return "BE" if is_engulf else "BS"
        else:
            return "SE" if is_engulf else "SS"

    if "PATTERN A" in text:
        return "PA"
    if "PATTERN B" in text:
        return "PB"
    if "PATTERN C" in text:
        return "PC"
    if "PATTERN D" in text:
        return "PD"
    if "PATTERN E" in text:
        return "PE"
    if "4 แท่ง" in raw or "PATTERN ใหม่ 4" in text:
        return "P4"
    if "DM SP" in text:
        m = re.search(r'\[C1:([A-Z_]+)\]', raw)
        if m:
            return m.group(1)
        return "DMSP"
    if "MARUBOZU" in text:
        return "MARU"
    if "FVG" in text and "นัยยะ" in raw:
        return "SIGFVG"
    if "FVG" in text:
        return "FVG"
    if "SCALPING" in text:
        return "S5"
    if "RSI DIVERGENCE" in text:
        return "RSI9"
    if "กินไส้" in raw or "SWING" in text:
        return "SWING"
    if "CRT" in text:
        return "CRT"
    if "FIBO" in text:
        # Pattern N → trigger_entry: 1=KRH1→50%, 2=KRH2→50%, 3=KRH3→KRH1
        if "PATTERN 1" in text:
            return "KRH1_50"
        if "PATTERN 2" in text:
            return "KRH2_50"
        if "PATTERN 3" in text:
            return "KRH3_KRH1"
        return "FIBO"
    return ""


def _build_order_comment(tf: str = "", sid="", pattern: str = "", fallback: str = "",
                         parallel_tfs: list = None, parallel_patterns: list = None,
                         order_index=None) -> str:
    # S10 MTF: ถ้า pattern มี "MTF [HTF→LTF]" ให้แทน tf เป็น "[HTF_LTF]"
    tf_label = tf
    if pattern and str(sid or "") == "10":
        left_bracket = pattern.find("[")
        right_bracket = pattern.find("]", left_bracket + 1) if left_bracket != -1 else -1
        if left_bracket != -1 and right_bracket != -1:
            inner = pattern[left_bracket + 1:right_bracket].strip()
            parts = None
            if "?" in inner:
                parts = inner.split("?", 1)
            elif "→" in inner:   # → Unicode right arrow (ใช้ใน pattern จริง)
                parts = inner.split("→", 1)
            elif "->" in inner:
                parts = inner.split("->", 1)
            if parts and len(parts) == 2:
                htf_tf = parts[0].strip()
                ltf_tf = parts[1].strip()
                if htf_tf and ltf_tf and htf_tf.isalnum() and ltf_tf.isalnum():
                    tf_label = f"[{htf_tf}_{ltf_tf}]"
    base = f"{tf_label}_S{sid}" if tf_label and sid else (f"{tf_label}" if tf_label else fallback)
    code = _pattern_comment_code(pattern, sid)
    if not code:
        return base

    candidate = f"{base}_{code}"

    if str(sid or "") == "10":
        candidate = base

    if str(sid or "") == "2" and parallel_tfs and len(parallel_tfs) > 1:
        tf_parts = [str(t).strip() for t in parallel_tfs if str(t).strip()]
        if tf_parts:
            parallel_comment = f"[{'_'.join(tf_parts)}]_S{sid}"
            if len(parallel_comment) <= 31:
                return parallel_comment

    if pattern:
        m_model = re.search(r"MODEL\s*([12])", pattern.upper())
        if m_model:
            candidate_with_model = f"{candidate}_#{m_model.group(1)}"
            if len(candidate_with_model) <= 31:
                candidate = candidate_with_model
        if str(sid or "") == "13":
            idx_text = str(order_index).strip() if order_index is not None else ""
            if idx_text in ("1", "2", "3"):
                candidate_with_tp = f"{candidate}_#{idx_text}"
                if len(candidate_with_tp) <= 31:
                    candidate = candidate_with_tp
            elif idx_text.upper() in ("L1", "L2", "L3"):
                candidate_with_tp = f"{candidate}_{idx_text.upper()}"
                if len(candidate_with_tp) <= 31:
                    candidate = candidate_with_tp
            else:
                m_tp = re.search(r"TP\s*([123])", pattern.upper())
                if m_tp:
                    candidate_with_tp = f"{candidate}_#{m_tp.group(1)}"
                    if len(candidate_with_tp) <= 31:
                        candidate = candidate_with_tp
    if len(candidate) > 31:
        return base

    # parallel: ต่อ TF ที่ซ้อนทับหลัง code เช่น Bot_M5_S2_FVG_M15M30
    if parallel_tfs and len(parallel_tfs) > 1:
        other_tfs = [t for t in parallel_tfs if t != tf]
        if other_tfs:
            suffix = "".join(other_tfs)
            full = f"{candidate}_{suffix}"
            return full if len(full) <= 31 else candidate

    return candidate

def connect_mt5():
    """เชื่อมต่อ MT5 — ถ้า initialize แล้วและ login อยู่แล้วไม่ต้อง login ซ้ำ"""
    if not mt5.initialize():
        return False
    # ตรวจว่า login อยู่แล้วหรือยัง
    info = mt5.account_info()
    if info is not None and info.login == MT5_LOGIN:
        return True  # เชื่อมอยู่แล้ว ไม่ต้อง login ซ้ำ
    return mt5.login(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)


def get_structure(rates, lookback=None):
    n = lookback if lookback else SWING_LOOKBACK
    s = rates[-n:]
    return {
        "swing_high": max(r['high'] for r in s),
        "swing_low":  min(r['low']  for r in s),
        "atr":        sum(r['high'] - r['low'] for r in s) / len(s)
    }


def find_swing_tp(rates, signal: str, entry: float, sl: float, n_long=40, tf: str = "") -> float | None:
    """
    หา TP ที่ Swing High/Low ที่ใกล้ที่สุด RR ≥ 1:1
    - ลอง HHLL swing (HHLLStrategy) ก่อน ถ้า tf ระบุ
    - Fallback: ค้นหาทั้ง Swing ย่อย (2 แท่งข้าง) และ Swing หลัก (4 แท่งข้าง)
    - เลือกอันที่ใกล้ที่สุดที่ RR ≥ 1:1
    """
    if len(rates) < 6:
        return None

    risk = abs(entry - sl)
    if risk <= 0:
        return None

    # ── HHLL swing TP (HHLLStrategy) ────────────────────────────
    if tf:
        try:
            from hhll_swing import get_swing_hl_pts
            sh_pt, sl_pt = get_swing_hl_pts(tf)
            if signal == "BUY" and sh_pt:
                tp = float(sh_pt["price"])
                if tp > entry and (tp - entry) / risk >= 1.0:
                    return round(tp, 2)
            elif signal == "SELL" and sl_pt:
                tp = float(sl_pt["price"])
                if tp < entry and (entry - tp) / risk >= 1.0:
                    return round(tp, 2)
        except Exception:
            pass

    # ค้นหาจากแท่งที่ปิดแล้ว ย้อนหลัง n_long แท่ง
    lookback = min(n_long + 2, len(rates) - 1)
    r = rates[-lookback:-1]

    candidates = []

    if signal == "BUY":
        for i in range(2, len(r)-2):
            h = float(r[i]['high'])
            if h <= entry:
                continue
            rr = (h - entry) / risk
            if rr < 1.0:
                continue
            # Swing High ย่อย (n=1) หรือ หลัก (n=2)
            minor = (h > float(r[i-1]['high']) and h > float(r[i+1]['high']))
            major = (h > float(r[i-2]['high']) and h > float(r[i-1]['high']) and
                     h > float(r[i+1]['high']) and h > float(r[i+2]['high']))
            if minor or major:
                candidates.append(h)

        if candidates:
            return round(min(candidates), 2)  # ใกล้ที่สุด RR≥1:1

    else:  # SELL
        for i in range(2, len(r)-2):
            l = float(r[i]['low'])
            if l >= entry:
                continue
            rr = (entry - l) / risk
            if rr < 1.0:
                continue
            # Swing Low ย่อย (n=1) หรือ หลัก (n=2)
            minor = (l < float(r[i-1]['low']) and l < float(r[i+1]['low']))
            major = (l < float(r[i-2]['low']) and l < float(r[i-1]['low']) and
                     l < float(r[i+1]['low']) and l < float(r[i+2]['low']))
            if minor or major:
                candidates.append(l)

        if candidates:
            return round(max(candidates), 2)  # ใกล้ที่สุด RR≥1:1

    return None  # ไม่เจอ Swing RR≥1:1 → fallback RR1:1


# ============================================================
#  Strategy 1
#
#  Pattern A — กลืนกิน:
#    BUY:  [1] เขียว Close > High[2] (ปิดเหนือไส้บนแดง[2])
#          [0] เขียว (สีเดียวกับ[1]) + อยู่ใกล้ Swing Low
#    SELL: [1] แดง Close < Low[2] (ปิดใต้ไส้ล่างเขียว[2])
#          [0] แดง (สีเดียวกับ[1]) + อยู่ใกล้ Swing High
#
#  Pattern B — ตำหนิ:
#    BUY:  [3] แดง
#          [2] เขียว + High[2] อยู่ใน range หรือเหนือ High[3]
#               + Body[2] >= 35% ของ Range[2]
#          [1] เขียว Close > High[2] (กลืนกินจริง)
#          [0] เขียว + อยู่ใกล้ Swing Low
#    SELL: [3] เขียว
#          [2] แดง + Low[2] อยู่ใน range หรือใต้ Low[3]
#               + Body[2] >= 35% ของ Range[2]
#          [1] แดง Close < Low[2] (กลืนกินจริง)
#          [0] แดง + อยู่ใกล้ Swing High
# ============================================================

def get_existing_tp(signal: str, entry: float = 0.0, tf: str = "", requester_sid: int = 0) -> float:
    """
    ถ้ามี Position เปิดอยู่แล้วที่ทิศทางเดียวกัน และ TF เดียวกัน → คืน TP ของ Position นั้น
    เพื่อให้ Order ใน TF เดียวกันใช้ TP ร่วมกัน

    - ถ้าส่ง tf มาด้วย จะ filter เฉพาะ position ที่มาจาก TF เดียวกัน
    - ถ้าส่ง entry มาด้วย จะตรวจ direction ของ TP vs entry
      BUY: TP ต้องสูงกว่า entry / SELL: TP ต้องต่ำกว่า entry
    """
    if requester_sid in (12, 13):
        return 0.0

    from trailing import position_tf as _pos_tf, position_sid as _pos_sid
    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        return 0.0
    for pos in positions:
        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        if pos_type != signal:
            continue
        if _pos_sid.get(pos.ticket) == 12:
            continue
        if pos.tp <= 0:
            continue
        # filter TF: ถ้าระบุ tf มา ต้อง match เท่านั้น
        if tf:
            pos_tf_name = _pos_tf.get(pos.ticket, "")
            if pos_tf_name and pos_tf_name != tf:
                continue
        existing = float(pos.tp)
        # ตรวจ direction ถ้ามี entry
        if entry > 0:
            if signal == "BUY" and existing <= entry:
                print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ get_existing_tp: BUY TP={existing:.2f} ≤ entry={entry:.2f} → ใช้ TP ใหม่แทน")
                return 0.0
            if signal == "SELL" and existing >= entry:
                print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ get_existing_tp: SELL TP={existing:.2f} ≥ entry={entry:.2f} → ใช้ TP ใหม่แทน")
                return 0.0
        return existing
    return 0.0


def open_order_stop(signal, volume, sl, tp, entry_price, tf="", sid="", pattern=""):
    """
    ตั้ง Stop Order ที่ entry_price (ท่า 4 นัยยะสำคัญ FVG)
    BUY  → BUY_STOP  (รอราคาขึ้นไปแตะ Swing High)
    SELL → SELL_STOP (รอราคาลงไปแตะ Swing Low)
    """
    tick = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        return {"success": False, "error": "ดึงราคาไม่ได้"}

    current = tick.ask if signal == "BUY" else tick.bid
    price   = entry_price

    info      = mt5.symbol_info(SYMBOL)
    spread_pts = info.spread * info.point if info else 0
    tol        = max(spread_pts, 0.30)

    if signal == "BUY":
        if price <= current + tol:
            return {
                "success": False, "skipped": True,
                "error": f"⏭️ Entry BUY STOP ต้องสูงกว่าราคาปัจจุบัน\nEntry:{price:.2f} | Ask:{current:.2f}"
            }
        ot = mt5.ORDER_TYPE_BUY_STOP
    else:
        if price >= current - tol:
            return {
                "success": False, "skipped": True,
                "error": f"⏭️ Entry SELL STOP ต้องต่ำกว่าราคาปัจจุบัน\nEntry:{price:.2f} | Bid:{current:.2f}"
            }
        ot = mt5.ORDER_TYPE_SELL_STOP

    # ── Triple Scale-Out: ขยาย volume ตาม TP เดิม (skip S13) ──
    base_volume = float(volume)
    send_volume, effective_steps = _scale_out_resolve_volume(
        base_volume, sid=sid, direction=signal, entry=price, tp=tp
    )
    is_scaled = bool(effective_steps)

    r = mt5.order_send({
        "action":       mt5.TRADE_ACTION_PENDING,
        "symbol":       SYMBOL,
        "volume":       send_volume,
        "type":         ot,
        "price":        price,
        "sl":           sl,
        "tp":           tp,
        "deviation":    20,
        "magic":        234001,
        "comment":      _build_order_comment(tf, sid, pattern, "Strategy4_Stop"),
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    })
    if r and r.retcode == mt5.TRADE_RETCODE_DONE:
        name = "BUY STOP" if signal == "BUY" else "SELL STOP"
        if is_scaled:
            _scale_out_register_ticket(r.order, signal, price, base_volume, send_volume,
                                       sid=sid, tp_original=tp,
                                       effective_steps=effective_steps)
        return {"success": True, "ticket": r.order, "price": price, "order_type": name,
                "scale_out": is_scaled, "scaled_volume": send_volume if is_scaled else None}
    err = r.retcode if r else "no result"
    return {"success": False, "error": f"{err}"}


def open_order(signal, volume, sl, tp, entry_price=None, tf="", sid="", pattern="",
               parallel_tfs=None, parallel_patterns=None, order_index=None):
    """
    ตั้ง Limit Order ที่ entry_price
    BUY  → BUY_LIMIT  (รอราคาลงมาแตะ)
    SELL → SELL_LIMIT (รอราคาขึ้นมาแตะ)
    """
    tick = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        return {"success": False, "error": "ดึงราคาไม่ได้"}

    current = tick.ask if signal == "BUY" else tick.bid

    # ใช้ entry_price ที่คำนวณจาก Pattern
    # ถ้าไม่มีให้ใช้ราคาปัจจุบัน
    price = entry_price if entry_price else current

    # ใช้เฉพาะ BUY LIMIT และ SELL LIMIT เท่านั้น
    # tolerance ตรงนี้ใช้แค่กันกรณี entry ชิดราคาปัจจุบันมากจน broker มองว่า
    # เป็นคำสั่งที่ "ผ่านจุดเข้าไปแล้ว" เท่านั้น จึงควรเล็กมาก
    # ไม่ควรใช้ระดับ spread ทั้งก้อน เพราะจะทำให้ limit ที่ยัง valid
    # ถูก skip เร็วเกินไป (เช่น S9 ที่ราคาใกล้ entry มาก)
    info = mt5.symbol_info(SYMBOL)
    point = float(info.point) if info and getattr(info, "point", 0) else 0.01
    tol = max(point * 2.0, 0.01)

    if signal == "BUY":
        # BUY_LIMIT: Entry ต้องต่ำกว่าราคาปัจจุบัน (ask) อย่างน้อย tol
        if price >= current - tol:
            return {
                "success": False,
                "skipped": True,
                "error": f"⏭️ ราคาผ่าน Entry BUY ไปแล้ว\nEntry:{price:.2f} | Ask:{current:.2f} | ต้องการ Entry < {current-tol:.2f}"
            }
        ot = mt5.ORDER_TYPE_BUY_LIMIT
    else:
        # SELL_LIMIT: Entry ต้องสูงกว่าราคาปัจจุบัน (bid) อย่างน้อย tol
        if price <= current + tol:
            return {
                "success": False,
                "skipped": True,
                "error": f"⏭️ ราคาผ่าน Entry SELL ไปแล้ว\nEntry:{price:.2f} | Bid:{current:.2f} | ต้องการ Entry > {current+tol:.2f}"
            }
        ot = mt5.ORDER_TYPE_SELL_LIMIT

    # ── Triple Scale-Out: ขยาย volume ตาม TP เดิม (dynamic steps) ──
    base_volume = float(volume)
    send_volume, effective_steps = _scale_out_resolve_volume(
        base_volume, sid=sid, direction=signal, entry=price, tp=tp
    )
    is_scaled = bool(effective_steps)

    r = mt5.order_send({
        "action":       mt5.TRADE_ACTION_PENDING,
        "symbol":       SYMBOL,
        "volume":       send_volume,
        "type":         ot,
        "price":        price,
        "sl":           sl,
        "tp":           tp,
        "deviation":    20,
        "magic":        234001,
        "comment":      _build_order_comment(
            tf, sid, pattern, "Strategy1_Limit",
            parallel_tfs=parallel_tfs,
            parallel_patterns=parallel_patterns,
            order_index=order_index,
        ),
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    })
    if r is None:
        err = mt5.last_error()
        return {"success": False, "error": f"order_send returned None — {err}"}
    if r is None:
        err = mt5.last_error()
        return {"success": False, "error": f"order_send returned None — {err}"}
    if r.retcode == mt5.TRADE_RETCODE_DONE:
        order_type_name = {
            mt5.ORDER_TYPE_BUY_LIMIT:   "BUY LIMIT",
            mt5.ORDER_TYPE_BUY_STOP:    "BUY STOP",
            mt5.ORDER_TYPE_SELL_LIMIT:  "SELL LIMIT",
            mt5.ORDER_TYPE_SELL_STOP:   "SELL STOP",
        }.get(ot, "LIMIT")
        if is_scaled:
            _scale_out_register_ticket(r.order, signal, price, base_volume, send_volume,
                                       sid=sid, tp_original=tp,
                                       effective_steps=effective_steps)
        return {"success": True, "ticket": r.order, "price": price, "order_type": order_type_name,
                "scale_out": is_scaled, "scaled_volume": send_volume if is_scaled else None}
    err_code = r.retcode if r else "no result"
    err_msg  = r.comment if r else ""
    if str(err_code) == "10027":
        return {"success": False, "error": "⚠️ AutoTrading ปิดอยู่ใน MT5 กด Ctrl+E ให้เป็นสีเขียว"}
    if str(err_code) == "10016":
        return {"success": False, "error": f"⚠️ Invalid stops (10016) — Entry:{price} SL:{sl} TP:{tp} | SL/TP ใกล้ราคาเกินไปหรือผิดทิศ"}
    return {"success": False, "error": f"{err_code} — {err_msg}"}


def open_order_market(signal, volume, sl, tp, tf="", sid="", pattern="", order_index=None):
    """
    Market order — fill ทันทีที่ราคาปัจจุบัน
    BUY  → ส่ง market BUY  (ask)
    SELL → ส่ง market SELL (bid)

    TSO (Triple Scale-Out): รองรับสำหรับทุก sid ยกเว้น S13 (มี logic แยก)
    เมื่อ SCALE_OUT_ENABLED=True → volume ×4, register TSO steps ใน scale_out_state
    trailing.py จะ partial-close ตาม steps และอัปเดต entry เป็น fill จริงอัตโนมัติ
    """
    tick = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        return {"success": False, "error": "ดึงราคาไม่ได้"}

    price = tick.ask if signal == "BUY" else tick.bid
    ot    = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL

    # ── Triple Scale-Out: ขยาย volume (skip S13 — มี logic แยก) ──
    base_volume = float(volume)
    send_volume, effective_steps = _scale_out_resolve_volume(
        base_volume, sid=sid, direction=signal, entry=price, tp=tp
    )
    is_scaled = bool(effective_steps)

    r = mt5.order_send({
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       SYMBOL,
        "volume":       send_volume,
        "type":         ot,
        "price":        price,
        "sl":           sl,
        "tp":           tp,
        "deviation":    20,
        "magic":        234001,
        "comment":      _build_order_comment(tf, sid, pattern, "Strategy_Market", order_index=order_index),
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    })
    if r is None:
        err = mt5.last_error()
        return {"success": False, "error": f"order_send returned None — {err}"}
    if r.retcode == mt5.TRADE_RETCODE_DONE:
        name = "BUY" if signal == "BUY" else "SELL"
        ticket = r.order
        if is_scaled and ticket:
            # ลงทะเบียน TSO — trailing.py จะอัปเดต entry เป็น fill จริงเมื่อเห็น position
            # (is_pending=True → trailing.py แก้ไขให้อัตโนมัติใน check_scale_out)
            _scale_out_register_ticket(
                ticket, signal, price, base_volume, send_volume,
                sid=sid, tp_original=tp,
                effective_steps=effective_steps,
            )
        return {"success": True, "ticket": ticket, "price": price, "order_type": name,
                "scale_out": is_scaled, "scaled_volume": send_volume if is_scaled else None}
    err_code = r.retcode if r else "no result"
    err_msg  = r.comment if r else ""
    if str(err_code) == "10027":
        return {"success": False, "error": "⚠️ AutoTrading ปิดอยู่ใน MT5 กด Ctrl+E ให้เป็นสีเขียว"}
    if str(err_code) == "10016":
        return {"success": False, "error": f"⚠️ Invalid stops (10016) — Entry:{price} SL:{sl} TP:{tp}"}
    return {"success": False, "error": f"{err_code} — {err_msg}"}


# ============================================================
#  Auto Scan — วน Loop ทุก Timeframe ที่เปิดอยู่
# ============================================================

# เก็บ last_traded per TF เพื่อกัน Order ซ้ำในแท่งเดิม
last_traded_per_tf   = {}  # {"H1": timestamp, ...} กัน order ซ้ำ
pb_pending           = {}  # {"H1_1234567": {entry, sl, tp, signal, ...}} Pattern B วิธี 2 รอราคาแตะ
fvg_pending          = {}  # {"H1_1234567": {signal, entry, sl, tp, gap_top, gap_bot, tf, candle_key}}

TF_SECONDS_MAP = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "M30": 1800,
    "H1": 3600,
    "H4": 14400,
    "H12": 43200,
    "D1": 86400,
}


def has_previous_bar_trade(tf_name: str, candle_time: int) -> bool:
    """เช็กว่าแท่งก่อนหน้าใน TF นี้เคยมี order ไปแล้วหรือยัง"""
    tf_secs = TF_SECONDS_MAP.get(tf_name)
    if not tf_secs:
        return False
    prev_traded = last_traded_per_tf.get(tf_name)
    return bool(prev_traded and (candle_time - prev_traded) == tf_secs)

def should_cancel_pending(rates, signal: str, entry: float) -> tuple:
    """
    ตรวจว่าควรยกเลิก Limit Order ที่รออยู่หรือไม่
    เงื่อนไขยกเลิก:
    1. ราคาผ่าน Entry ไปแล้ว (ไม่สามารถตั้ง Limit ได้)
    2. แท่งล่าสุดปิดกลืนกิน Swing High ย่อย (BUY) หรือ Swing Low ย่อย (SELL)
       → โอกาสที่ราคาจะย้อนมาแตะ Entry ลดลงมาก

    Return: (should_cancel: bool, reason: str)
    """
    if len(rates) < 3:
        return False, ""

    tick = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        return False, ""

    # ── Condition 1 ถูกปิด ── (ราคาผ่าน Entry ไปไกล)
    # ── Condition 2 ถูกลบ ──
    # ── Condition 3 ถูกปิด ── (กลืนกิน Swing High/Low)

    return False, ""
