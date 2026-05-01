from config import *


def _pattern_comment_code(pattern: str) -> str:
    text = (pattern or "").upper()
    raw = pattern or ""

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
    return ""


def _build_order_comment(tf: str = "", sid="", pattern: str = "", fallback: str = "", parallel_tfs: list = None) -> str:
    base = f"Bot_{tf}_S{sid}" if tf and sid else (f"Bot_{tf}" if tf else fallback)
    code = _pattern_comment_code(pattern)
    if not code:
        return base

    candidate = f"{base}_{code}"
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


def find_swing_tp(rates, signal: str, entry: float, sl: float, n_long=40) -> float | None:
    """
    หา TP ที่ Swing High/Low ที่ใกล้ที่สุด RR ≥ 1:1
    - ค้นหาทั้ง Swing ย่อย (2 แท่งข้าง) และ Swing หลัก (4 แท่งข้าง)
    - เลือกอันที่ใกล้ที่สุดที่ RR ≥ 1:1
    - ไม่จำกัด RR สูงสุด (ยิ่งไกลยิ่งดี ถ้าเป็น Swing จริง)
    """
    if len(rates) < 6:
        return None

    risk = abs(entry - sl)
    if risk <= 0:
        return None

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

def get_existing_tp(signal: str, entry: float = 0.0, tf: str = "") -> float:
    """
    ถ้ามี Position เปิดอยู่แล้วที่ทิศทางเดียวกัน และ TF เดียวกัน → คืน TP ของ Position นั้น
    เพื่อให้ Order ใน TF เดียวกันใช้ TP ร่วมกัน

    - ถ้าส่ง tf มาด้วย จะ filter เฉพาะ position ที่มาจาก TF เดียวกัน
    - ถ้าส่ง entry มาด้วย จะตรวจ direction ของ TP vs entry
      BUY: TP ต้องสูงกว่า entry / SELL: TP ต้องต่ำกว่า entry
    """
    from trailing import position_tf as _pos_tf
    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        return 0.0
    for pos in positions:
        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        if pos_type != signal:
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

    r = mt5.order_send({
        "action":       mt5.TRADE_ACTION_PENDING,
        "symbol":       SYMBOL,
        "volume":       volume,
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
        return {"success": True, "ticket": r.order, "price": price, "order_type": name}
    err = r.retcode if r else "no result"
    return {"success": False, "error": f"{err}"}


def open_order(signal, volume, sl, tp, entry_price=None, tf="", sid="", pattern="", parallel_tfs=None):
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
    # tolerance = spread ประมาณ 0.30 (3 จุด) เผื่อ slippage เล็กน้อย
    info = mt5.symbol_info(SYMBOL)
    spread_pts = info.spread * info.point if info else 0
    tol = max(spread_pts, 0.30)

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

    r = mt5.order_send({
        "action":       mt5.TRADE_ACTION_PENDING,
        "symbol":       SYMBOL,
        "volume":       volume,
        "type":         ot,
        "price":        price,
        "sl":           sl,
        "tp":           tp,
        "deviation":    20,
        "magic":        234001,
        "comment":      _build_order_comment(tf, sid, pattern, "Strategy1_Limit", parallel_tfs=parallel_tfs),
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
        return {"success": True, "ticket": r.order, "price": price, "order_type": order_type_name}
    err_code = r.retcode if r else "no result"
    err_msg  = r.comment if r else ""
    if str(err_code) == "10027":
        return {"success": False, "error": "⚠️ AutoTrading ปิดอยู่ใน MT5 กด Ctrl+E ให้เป็นสีเขียว"}
    if str(err_code) == "10016":
        return {"success": False, "error": f"⚠️ Invalid stops (10016) — Entry:{price} SL:{sl} TP:{tp} | SL/TP ใกล้ราคาเกินไปหรือผิดทิศ"}
    return {"success": False, "error": f"{err_code} — {err_msg}"}


def open_order_market(signal, volume, sl, tp, tf="", sid="", pattern=""):
    """
    Market order — fill ทันทีที่ราคาปัจจุบัน
    BUY  → ส่ง market BUY  (ask)
    SELL → ส่ง market SELL (bid)
    """
    tick = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        return {"success": False, "error": "ดึงราคาไม่ได้"}

    price = tick.ask if signal == "BUY" else tick.bid
    ot    = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL

    r = mt5.order_send({
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       SYMBOL,
        "volume":       volume,
        "type":         ot,
        "price":        price,
        "sl":           sl,
        "tp":           tp,
        "deviation":    20,
        "magic":        234001,
        "comment":      _build_order_comment(tf, sid, pattern, "Strategy_Market"),
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    })
    if r is None:
        err = mt5.last_error()
        return {"success": False, "error": f"order_send returned None — {err}"}
    if r.retcode == mt5.TRADE_RETCODE_DONE:
        name = "BUY" if signal == "BUY" else "SELL"
        return {"success": True, "ticket": r.order, "price": price, "order_type": name}
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

