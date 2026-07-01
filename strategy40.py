"""
strategy40.py — S40 Elliott Wave (simplified 5-wave impulse, wave-4-completion entry)
RESEARCH/BACKTEST-ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ standalone 100% — ไม่ถูก import โดย scanner.py/trailing.py/main.py, ไม่มี wiring เข้า live

⚠️ หมายเหตุ: Elliott Wave มี ambiguity สูงในการนับ wave (นักวิเคราะห์ต่างคนนับต่างกันได้) เวอร์ชันนี้
เป็น **rule-based proxy แบบเข้มงวด** ไม่ใช่ Elliott Wave เต็มรูปแบบ — ใช้ zigzag pivot (ขั้นต่ำ
ZIGZAG_MIN_ATR x ATR ต่อขา) แล้วตรวจกฎ 3 ข้อหลักของ impulsive wave (wave2 ไม่ retrace เกิน 100%
ของ wave1, wave3 ยาวกว่า wave1, wave4 ไม่ทับ territory ของ wave1) บนชุด pivot ล่าสุด 5 จุด
(wave0-1-2-3-4) แล้วเข้า BUY/SELL ต่อทิศ wave3 ตอนเสร็จ wave4 (คาดหวัง wave5) ยืนยันด้วย htf_trend
"""

S40_DEFAULTS = {
    "ENTRY_TF": "M5",
    "ZIGZAG_MIN_ATR": 1.5,         # ขนาดขั้นต่ำของแต่ละขา zigzag (กัน noise/นับ wave เล็กเกินไป)
    "ZIGZAG_LOOKBACK_BARS": 150,   # หา zigzag pivot ย้อนหลัง N แท่ง
    "MAX_WAVE4_AGE_BARS": 15,      # wave4 (pivot ล่าสุด) ต้องเกิดภายใน N แท่ง ไม่งั้นถือว่าเก่าเกินไป
    "ENTRY_BREAK_ATR_MULT": 0.1,   # ต้อง breakout เลย wave4 pivot ไปในทิศ wave5 >= mult x ATR
    "SL_ATR_MULT": 1.0,
    "TP_RR": 1.5,
    "MAX_RISK_ATR_MULT": 5.0,
    "MIN_GAP_BARS": 1,
    "SESSION_FILTER": True,
    "SESSIONS": [("14:00", "23:00")],

    "RISK_PCT": 0.5,
    "DD_CONTROL": "circuit_breaker",
    "CONSEC_LOSS_TRIGGER": 3,
    "REDUCED_RISK_PCT": 0.4,
    "COOLDOWN_TRADES": 10,

    "CONFIRMATION_TYPE": "htf_trend",
    "HTF_TF": "M15",
    "HTF_EMA_PERIOD": 50,
    "HTF_SLOPE_BARS": 5,
    "ADX_PERIOD": 14,
    "ADX_MIN_THRESHOLD": 0.0,
}


def _cfg(cfg, key):
    if cfg and key in cfg:
        return cfg[key]
    return S40_DEFAULTS[key]


def _calc_atr(rates, period=14):
    n = len(rates)
    if n == 0:
        return 0.0
    trs = []
    for i in range(n):
        h = float(rates[i]["high"]); l = float(rates[i]["low"])
        if i == 0:
            trs.append(h - l)
        else:
            pc = float(rates[i - 1]["close"])
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return sum(trs) / len(trs) if trs else 0.0
    atr = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
    return atr


def _in_session(dt_bkk, cfg):
    if not _cfg(cfg, "SESSION_FILTER"):
        return True
    if dt_bkk is None:
        return True
    from datetime import time
    cur = dt_bkk.time()
    for start_str, end_str in _cfg(cfg, "SESSIONS"):
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        if time(sh, sm) <= cur < time(eh, em):
            return True
    return False


def _zigzag_pivots(closed_rates, atr, min_mult, lookback):
    """
    หา zigzag pivot สลับ high/low ย้อนหลัง lookback แท่ง ขั้นต่ำต่อขา = min_mult x ATR
    คืน list of (idx, price, "H"/"L") เรียงตามเวลา (เก่า->ใหม่)
    """
    n = len(closed_rates)
    start = max(0, n - lookback)
    min_move = min_mult * atr
    if min_move <= 0:
        return []

    pivots = []
    direction = None  # "up" or "down" จาก pivot ล่าสุดไปยัง extreme ปัจจุบัน
    last_pivot_idx = start
    last_pivot_price = float(closed_rates[start]["close"])
    extreme_idx = start
    extreme_price = last_pivot_price

    for i in range(start + 1, n):
        h = float(closed_rates[i]["high"]); l = float(closed_rates[i]["low"])
        if direction in (None, "up"):
            if h > extreme_price:
                extreme_price = h; extreme_idx = i
            if extreme_price - l >= min_move and extreme_idx != last_pivot_idx:
                pivots.append((extreme_idx, extreme_price, "H"))
                last_pivot_idx, last_pivot_price = extreme_idx, extreme_price
                extreme_idx, extreme_price = i, l
                direction = "down"
                continue
        if direction in (None, "down"):
            if l < extreme_price:
                extreme_price = l; extreme_idx = i
            if h - extreme_price >= min_move and extreme_idx != last_pivot_idx:
                pivots.append((extreme_idx, extreme_price, "L"))
                last_pivot_idx, last_pivot_price = extreme_idx, extreme_price
                extreme_idx, extreme_price = i, h
                direction = "up"
                continue
    return pivots


def _check_impulse(pivots):
    """
    ตรวจ 5 pivot ล่าสุด (p0,p1,p2,p3,p4) ว่าเข้ากฎ impulsive wave หรือไม่
    คืน (direction, p4_idx, p4_price) หรือ None
    """
    if len(pivots) < 5:
        return None
    p0, p1, p2, p3, p4 = pivots[-5:]

    if p0[2] == "L" and p1[2] == "H" and p2[2] == "L" and p3[2] == "H" and p4[2] == "L":
        wave1 = p1[1] - p0[1]
        wave2 = p1[1] - p2[1]
        wave3 = p3[1] - p2[1]
        wave4 = p3[1] - p4[1]
        if wave1 <= 0 or wave3 <= 0:
            return None
        if wave2 >= wave1:
            return None
        if wave3 <= wave1:
            return None
        if p4[1] <= p1[1]:
            return None
        return ("BUY", p4[0], p4[1])

    if p0[2] == "H" and p1[2] == "L" and p2[2] == "H" and p3[2] == "L" and p4[2] == "H":
        wave1 = p0[1] - p1[1]
        wave2 = p2[1] - p1[1]
        wave3 = p2[1] - p3[1]
        wave4 = p4[1] - p3[1]
        if wave1 <= 0 or wave3 <= 0:
            return None
        if wave2 >= wave1:
            return None
        if wave3 <= wave1:
            return None
        if p4[1] >= p1[1]:
            return None
        return ("SELL", p4[0], p4[1])

    return None


def detect_s40(rates, tf: str = "", dt_bkk=None, cfg: dict | None = None, htf_ctx: dict | None = None):
    lb = int(_cfg(cfg, "ZIGZAG_LOOKBACK_BARS"))
    need = lb + 20
    if rates is None or len(rates) < min(need, 60):
        return {"signal": "WAIT", "reason": "S40: ข้อมูลไม่พอ"}
    if not _in_session(dt_bkk, cfg):
        return {"signal": "WAIT", "reason": "S40: นอก session"}

    closed = rates[:-1]
    atr = _calc_atr(closed, 14)
    if not atr or atr <= 0:
        return {"signal": "WAIT", "reason": "S40: ATR ไม่ได้"}

    pivots = _zigzag_pivots(closed, atr, float(_cfg(cfg, "ZIGZAG_MIN_ATR")), lb)
    impulse = _check_impulse(pivots)
    if impulse is None:
        return {"signal": "WAIT", "reason": "S40: ไม่พบ impulsive 5-wave ที่ครบกฎ"}
    direction, p4_idx, p4_price = impulse

    age = (len(closed) - 1) - p4_idx
    if age > int(_cfg(cfg, "MAX_WAVE4_AGE_BARS")):
        return {"signal": "WAIT", "reason": "S40: wave4 เก่าเกินไป"}

    cur = closed[-1]
    cc = float(cur["close"])
    break_buf = float(_cfg(cfg, "ENTRY_BREAK_ATR_MULT")) * atr

    if direction == "BUY":
        if cc < p4_price + break_buf:
            return {"signal": "WAIT", "reason": "S40: ยังไม่ breakout เหนือ wave4 (รอ wave5)"}
        entry = round(cc, 2)
        sl = round(p4_price - float(_cfg(cfg, "SL_ATR_MULT")) * atr, 2)
    else:
        if cc > p4_price - break_buf:
            return {"signal": "WAIT", "reason": "S40: ยังไม่ breakout ใต้ wave4 (รอ wave5)"}
        entry = round(cc, 2)
        sl = round(p4_price + float(_cfg(cfg, "SL_ATR_MULT")) * atr, 2)

    conf_type = _cfg(cfg, "CONFIRMATION_TYPE")
    if conf_type != "none":
        if htf_ctx is None:
            return {"signal": "WAIT", "reason": "S40: ไม่มี HTF context"}
        if conf_type == "htf_trend":
            adx_min = float(_cfg(cfg, "ADX_MIN_THRESHOLD"))
            if adx_min > 0 and htf_ctx.get("adx", 0.0) < adx_min:
                return {"signal": "WAIT", "reason": "S40: ADX(HTF) ไม่ผ่าน"}
            if direction == "BUY" and not htf_ctx.get("trend_up", False):
                return {"signal": "WAIT", "reason": "S40: HTF ไม่ขึ้น"}
            if direction == "SELL" and not htf_ctx.get("trend_down", False):
                return {"signal": "WAIT", "reason": "S40: HTF ไม่ลง"}

    rr = float(_cfg(cfg, "TP_RR"))
    max_risk_mult = float(_cfg(cfg, "MAX_RISK_ATR_MULT"))
    if direction == "BUY":
        risk = entry - sl
        tp = round(entry + rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp > entry):
            return {"signal": "WAIT", "reason": "S40: risk ผิดปกติ"}
    else:
        risk = sl - entry
        tp = round(entry - rr * risk, 2)
        if not (0 < risk <= max_risk_mult * atr and tp < entry):
            return {"signal": "WAIT", "reason": "S40: risk ผิดปกติ"}

    b = closed[-1]
    return {
        "signal": direction, "entry": entry, "sl": sl, "tp": tp,
        "pattern": f"ท่าที่ 40 ElliottWave5+{conf_type} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"wave4=[{p4_price:.2f}]\n"
                  f"entry `{entry:.2f}` SL `{sl:.2f}` TP `{tp:.2f}` (RR {rr})",
        "order_mode": "market", "signal_bar_time": int(b["time"]), "atr_at_signal": atr,
        "confirmation_type": conf_type,
    }


def strategy_40(rates, tf: str = "", cfg: dict | None = None):
    """⚠️ ไม่มีจุดใดใน scanner.py/trailing.py/main.py เรียก — standalone จริง"""
    return detect_s40(rates, tf=tf, dt_bkk=None, cfg=cfg, htf_ctx=None)
