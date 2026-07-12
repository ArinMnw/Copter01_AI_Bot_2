# -*- coding: utf-8 -*-
"""
S110: The Fractal Alignment — The Perfect Storm (H4+H1+M15 โครงสร้างตรงกัน + M5 pullback)

ทำไมรอบนี้ต่างจากที่เคย falsify:
  - S100 v1 ใช้ "EMA slope" แทนเทรนด์ → EMA lag และไม่ใช่โครงสร้าง
  - S104 ใช้ CHoCH ทีละ TF เดี่ยวๆ → จับ "การเปลี่ยน" ไม่ใช่ "ความต่อเนื่อง"
  S110 คือ fractal alignment แท้: อ่าน swing structure (HH/HL vs LH/LL)
  จาก H4, H1, M15 ที่ resample จากแท่ง M5 จริง — ทั้งสามต้องชี้ทางเดียวกัน
  "ห้ามขัดแย้งแม้แต่ TF เดียว" แล้วค่อยรอ M5 pullback เข้า retrace ของ
  impulse ล่าสุด → เข้า LIMIT ตามเทรนด์ใหญ่

ตรรกะ:
  1. Resample M5 → M15/H1/H4 (เฉพาะแท่ง M5 ที่ปิดแล้ว — no look-ahead;
     แท่ง TF ใหญ่ใบสุดท้ายที่ยังไม่ครบช่วงเวลาจะถูกตัดทิ้ง)
  2. Structure trend ต่อ TF: pivot 2/2 → uptrend = HH & HL / downtrend = LL & LH
     (ใช้ swing 2 คู่ล่าสุดที่ยืนยันแล้ว) — TF ไหน "neutral" = ไม่ align
  3. ทั้ง 3 TF ต้องตรงกัน → มองหา M5 impulse leg ล่าสุดตามทิศเทรนด์
     (จาก swing M5 ล่าสุด → extreme ปัจจุบัน, ขนาด >= MIN_LEG_ATR)
  4. Entry: LIMIT ที่ retrace RETRACE ของ leg / SL หลัง swing ต้นทาง + buf
     TP = RR (เทรนด์ใหญ่หนุน — เป้า 2R)
  5. เข้าเฉพาะเมื่อราคายังไม่ถึงจุด retrace (รอ pullback มาหา ไม่ไล่)

กฎเหล็ก Reality Check: แท่งปิดแล้วเท่านั้น + limit fill ทะลุ spread + SL-first (sim)
"""

DEFAULT_CFG = {
    "TF_SECS": (900, 3600, 14400),   # M15, H1, H4
    "HTF_PIVOT": 2,                  # pivot left/right บน TF ใหญ่
    "HTF_SCAN_BARS": 60,             # แท่ง TF ใหญ่ที่ใช้หา structure
    "M5_PIVOT": 3,
    "M5_SCAN_BARS": 80,
    "MIN_LEG_ATR": 3.0,              # impulse leg M5 ขั้นต่ำ (x ATR) — sweep: 3.0 ดีสุด (leg เล็ก = noise)
    "ENTRY_RETRACE": 0.5,
    "SL_BUF_ATR": 0.5,
    "TP_RR": 1.5,  # sweep: 1.5 ชนะ 2.0/3.0 ชัด — pullback ตามเทรนด์ไม่ควรโลภ
    "TIME_FILTER_ENABLED": True,
    "BLOCK_HOURS": (4, 5, 6),
    "ML_FILTER_ENABLED": False,
    "ML_SCORE_THRESHOLD": 0.55,
}


def _atr(rates, period=14):
    trs = []
    for i in range(len(rates) - period, len(rates)):
        h, l = float(rates[i]["high"]), float(rates[i]["low"])
        pc = float(rates[i - 1]["close"])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs)


def _resample(rates, tf_secs):
    """รวมแท่ง M5 เป็นแท่ง TF ใหญ่ — ตัดแท่งใบสุดท้ายที่ยังไม่ครบช่วงทิ้ง"""
    out = []
    cur_key = None
    cur = None
    for r in rates:
        t = int(r["time"])
        key = t // tf_secs
        if key != cur_key:
            if cur is not None:
                out.append(cur)
            cur_key = key
            cur = {"high": float(r["high"]), "low": float(r["low"])}
        else:
            cur["high"] = max(cur["high"], float(r["high"]))
            cur["low"] = min(cur["low"], float(r["low"]))
    # ใบสุดท้าย (cur) ยังไม่ปิดครบช่วง — ไม่ append
    return out


def _pivots(bars, left, right, scan):
    n = len(bars)
    highs, lows = [], []
    start = max(left, n - scan)
    for i in range(start, n - right):
        h, l = bars[i]["high"], bars[i]["low"]
        if all(bars[j]["high"] < h for j in range(i - left, i + right + 1) if j != i):
            highs.append((i, h))
        if all(bars[j]["low"] > l for j in range(i - left, i + right + 1) if j != i):
            lows.append((i, l))
    return highs, lows


def _structure_trend(bars, pivot, scan):
    """'UP' = HH+HL / 'DOWN' = LL+LH / None = ไม่ชัด"""
    if len(bars) < pivot * 2 + 6:
        return None
    highs, lows = _pivots(bars, pivot, pivot, scan)
    if len(highs) < 2 or len(lows) < 2:
        return None
    hh = highs[-1][1] > highs[-2][1]
    hl = lows[-1][1] > lows[-2][1]
    ll = lows[-1][1] < lows[-2][1]
    lh = highs[-1][1] < highs[-2][1]
    if hh and hl:
        return "UP"
    if ll and lh:
        return "DOWN"
    return None


def detect_s110(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    # ต้องมีข้อมูลพอสำหรับ H4 structure (~40 แท่ง H4 = 1920 M5)
    if len(rates) < 2000:
        return {"signal": "WAIT", "reason": "Not enough data for H4 structure"}

    if c["TIME_FILTER_ENABLED"] and dt_bkk is not None:
        if dt_bkk.hour in c["BLOCK_HOURS"]:
            return {"signal": "WAIT", "reason": f"Blocked hour {dt_bkk.hour}"}

    atr = _atr(rates)
    if atr <= 0:
        return {"signal": "WAIT", "reason": "ATR zero"}

    # --- 1-2. Fractal alignment ทั้ง 3 TF ---
    trends = []
    for tf_secs in c["TF_SECS"]:
        bars = _resample(rates, tf_secs)
        trends.append(_structure_trend(bars, int(c["HTF_PIVOT"]), int(c["HTF_SCAN_BARS"])))
    if any(t is None for t in trends) or len(set(trends)) != 1:
        return {"signal": "WAIT", "reason": f"TF not aligned {trends}"}
    direction = "BUY" if trends[0] == "UP" else "SELL"

    # --- 3. M5 impulse leg ล่าสุดตามทิศ ---
    m5_bars = [{"high": float(r["high"]), "low": float(r["low"])} for r in rates]
    highs, lows = _pivots(m5_bars, int(c["M5_PIVOT"]), int(c["M5_PIVOT"]),
                          int(c["M5_SCAN_BARS"]))
    last_close = float(rates[-1]["close"])

    def _ml_ok(entry):
        if not c["ML_FILTER_ENABLED"]:
            return True, 1.0
        import ml_scoring
        prob = ml_scoring.score_signal('XAUUSD.iux', tf, direction, entry,
                                       dt_bkk, historical_rates=rates)
        return prob >= float(c["ML_SCORE_THRESHOLD"]), prob

    if direction == "BUY":
        if not lows:
            return {"signal": "WAIT", "reason": "No M5 swing low"}
        base_idx, base = lows[-1]
        # extreme หลัง swing = ปลาย impulse
        peak = max(float(r["high"]) for r in rates[base_idx:])
        leg = peak - base
        if leg < atr * float(c["MIN_LEG_ATR"]):
            return {"signal": "WAIT", "reason": "Impulse leg too small"}
        entry = peak - leg * float(c["ENTRY_RETRACE"])
        if last_close <= entry:
            return {"signal": "WAIT", "reason": "Pullback already past entry"}
        sl = base - max(1.5, atr * float(c["SL_BUF_ATR"]))
        risk = entry - sl
        if risk <= 0:
            return {"signal": "WAIT", "reason": "Invalid risk"}
        tp = entry + risk * float(c["TP_RR"])
    else:
        if not highs:
            return {"signal": "WAIT", "reason": "No M5 swing high"}
        base_idx, base = highs[-1]
        trough = min(float(r["low"]) for r in rates[base_idx:])
        leg = base - trough
        if leg < atr * float(c["MIN_LEG_ATR"]):
            return {"signal": "WAIT", "reason": "Impulse leg too small"}
        entry = trough + leg * float(c["ENTRY_RETRACE"])
        if last_close >= entry:
            return {"signal": "WAIT", "reason": "Pullback already past entry"}
        sl = base + max(1.5, atr * float(c["SL_BUF_ATR"]))
        risk = sl - entry
        if risk <= 0:
            return {"signal": "WAIT", "reason": "Invalid risk"}
        tp = entry - risk * float(c["TP_RR"])

    ok, prob = _ml_ok(entry)
    if not ok:
        return {"signal": "WAIT", "reason": f"blocked by ML ({prob:.2f})"}

    return {
        "signal": direction,
        "entry": round(entry, 2),
        "sl": round(sl, 2),
        "tp": round(tp, 2),
        "order_type": "limit",
        "pattern": f"S110 Fractal Align {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": (f"M15/H1/H4 all {trends[0]}, M5 leg {leg:.2f} "
                   f"retrace {float(c['ENTRY_RETRACE'])*100:.0f}%"),
        "candles": [rates[-1]],
    }
