# -*- coding: utf-8 -*-
"""
S104: Macro Trend Rider — H1 Structure Shift Swing (The Paradigm Shift)

ฉีกจาก S99-S103 อย่างไร:
  ทั้งตระกูลเดิมอยู่บน M5 ถือไม้เป็นนาที-ชั่วโมง กิน 1-3 R
  S104 ขยับขึ้น H1: อ่าน "การเปลี่ยนฝั่งของโครงสร้างใหญ่" (CHoCH) แล้วถือข้ามวัน
  กินคำใหญ่ RR 1:3+ — มิติเวลาใหม่ทั้งหมด correlation กับ M5 family ต่ำโดยธรรมชาติ

ตรรกะ (The Alpha):
  1. Structure Map บน H1 — pivot swing (3/3) ไล่ลำดับ HH/HL/LH/LL
  2. CHoCH (Change of Character):
     - SELL: โครงสร้างขาขึ้น (swing high ล่าสุด > ตัวก่อน) แล้วแท่ง H1 "close"
       ทะลุใต้ swing low ล่าสุด = ขาขึ้นหักคอ
     - BUY: กลับด้าน
  3. Displacement — แท่ง CHoCH ต้องมี body ≥ k×ATR(H1) ยืนยัน conviction
  4. Entry แบบมีวินัย — LIMIT ที่ retrace 50% ของ leg (จาก peak/trough → CHoCH close)
     ไม่ไล่ราคาหลัง CHoCH (จุดที่คนส่วนใหญ่โดนย้อน)
  5. SL หลัง peak/trough เดิม + buffer / TP = RR 3 (หรือ trailing โครงสร้าง)
  6. ไม่มี time filter — swing ข้ามวันข้ามเซสชัน

เป้า: ~1-2 ไม้/สัปดาห์, PF > 3, RR จริงต่อไม้ 1:3+
"""

DEFAULT_CFG = {
    "SWING_LEFT": 4,   # sweep 365d: pivot 4/4 ชนะ 3/3 ชัด (H1 half พลิกเป็นบวก)
    "SWING_RIGHT": 4,
    "SWING_SCAN_BARS": 120,
    "STRUCT_CONFIRM": True,     # ต้องเห็นโครงสร้างเดิมชัด (HH ล่าสุด > ตัวก่อน สำหรับ SELL)
    "CHOCH_MAX_AGE": 2,         # CHoCH ต้องเพิ่งเกิดภายใน N แท่งล่าสุด
    "DISP_BODY_ATR": 0.8,       # body แท่ง CHoCH ≥ k×ATR(H1)
    "ENTRY_RETRACE": 0.38,      # limit ที่ retrace ของ leg (sweep: 0.38 > 0.5 > 0.62)
    "SL_BUF_ATR": 0.5,
    "TP_RR": 3.0,
    "TRAIL_ENABLED": False,     # v1 ใช้ fixed RR (swing ต้องปล่อยให้วิ่ง)
    "TRAIL_BE_RR": 1.5,
    "TRAIL_ATR_MULT": 2.5,
    "TP_RR_MAX": 6.0,
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


def _find_swings(rates, left, right, scan_bars):
    n = len(rates)
    highs, lows = [], []
    start = max(left, n - scan_bars)
    for i in range(start, n - right):
        h = float(rates[i]["high"])
        l = float(rates[i]["low"])
        if all(float(rates[j]["high"]) < h for j in range(i - left, i + right + 1) if j != i):
            highs.append((i, h))
        if all(float(rates[j]["low"]) > l for j in range(i - left, i + right + 1) if j != i):
            lows.append((i, l))
    return highs, lows


def detect_s104(rates, tf="H1", dt_bkk=None, cfg=None, **kwargs):
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    if len(rates) < 140:
        return {"signal": "WAIT", "reason": "Not enough data"}

    atr = _atr(rates)
    if atr <= 0:
        return {"signal": "WAIT", "reason": "ATR zero"}

    sw_highs, sw_lows = _find_swings(
        rates, int(c["SWING_LEFT"]), int(c["SWING_RIGHT"]), int(c["SWING_SCAN_BARS"]))
    if len(sw_highs) < 2 or len(sw_lows) < 2:
        return {"signal": "WAIT", "reason": "Structure not mapped"}

    n = len(rates)
    last = rates[-1]
    l_o, l_c = float(last["open"]), float(last["close"])
    l_h, l_l = float(last["high"]), float(last["low"])
    body = abs(l_c - l_o)
    disp_ok = body >= atr * float(c["DISP_BODY_ATR"])

    # swing ล่าสุด (ยืนยันแล้วด้วย right bars)
    (h1_idx, h1_p), (h0_idx, h0_p) = sw_highs[-2], sw_highs[-1]
    (l1_idx, l1_p), (l0_idx, l0_p) = sw_lows[-2], sw_lows[-1]

    def _ml_ok(direction, entry):
        if not c["ML_FILTER_ENABLED"]:
            return True, 1.0
        import ml_scoring
        prob = ml_scoring.score_signal('XAUUSD.iux', tf, direction, entry,
                                       dt_bkk, historical_rates=rates)
        return prob >= float(c["ML_SCORE_THRESHOLD"]), prob

    def _result(direction, entry, sl, tp, why):
        risk = (entry - sl) if direction == "BUY" else (sl - entry)
        res = {
            "signal": direction,
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "order_type": "limit",
            "pattern": f"S104 Macro CHoCH {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
            "reason": why,
            "candles": [last],
        }
        if c["TRAIL_ENABLED"]:
            res["trail"] = {
                "be_rr": float(c["TRAIL_BE_RR"]),
                "atr_mult": float(c["TRAIL_ATR_MULT"]),
                "atr": atr,
                "risk": risk,
            }
        return res

    # ---------- SELL CHoCH: ขาขึ้นหักคอ ----------
    # โครงสร้างขาขึ้น: HH ล่าสุดสูงกว่าตัวก่อน (และ peak เกิดหลัง swing low ล่าสุด)
    up_struct = (h0_p > h1_p) if c["STRUCT_CONFIRM"] else True
    if up_struct and disp_ok and l_c < l_o:
        # CHoCH: close ใต้ swing low ล่าสุด และ low นั้นเกิดก่อน peak ปัจจุบัน
        ref_low = l0_p if l0_idx > l1_idx else l1_p
        if l_c < ref_low and h0_idx > l0_idx - 50:
            # เพิ่งหลุด: แท่งก่อนหน้า CHOCH_MAX_AGE แท่งยังปิดเหนือ ref_low
            fresh = all(float(rates[-1 - k]["close"]) >= ref_low
                        for k in range(1, int(c["CHOCH_MAX_AGE"]) + 1))
            if fresh:
                peak = h0_p
                leg_hi, leg_lo = peak, l_c
                entry = leg_lo + (leg_hi - leg_lo) * float(c["ENTRY_RETRACE"])
                sl = peak + max(2.0, atr * float(c["SL_BUF_ATR"]))
                risk = sl - entry
                if risk > 0:
                    rr = float(c["TP_RR_MAX"]) if c["TRAIL_ENABLED"] else float(c["TP_RR"])
                    tp = entry - risk * rr
                    ok, prob = _ml_ok("SELL", entry)
                    if not ok:
                        return {"signal": "WAIT", "reason": f"blocked by ML ({prob:.2f})"}
                    return _result("SELL", entry, sl, tp,
                                   (f"CHoCH down: close {l_c:.2f} < HL {ref_low:.2f} "
                                    f"after HH {peak:.2f}, disp {body:.2f}/{atr:.2f}ATR"))

    # ---------- BUY CHoCH: ขาลงหักคอ ----------
    down_struct = (l0_p < l1_p) if c["STRUCT_CONFIRM"] else True
    if down_struct and disp_ok and l_c > l_o:
        ref_high = h0_p if h0_idx > h1_idx else h1_p
        if l_c > ref_high and l0_idx > h0_idx - 50:
            fresh = all(float(rates[-1 - k]["close"]) <= ref_high
                        for k in range(1, int(c["CHOCH_MAX_AGE"]) + 1))
            if fresh:
                trough = l0_p
                leg_lo, leg_hi = trough, l_c
                entry = leg_hi - (leg_hi - leg_lo) * float(c["ENTRY_RETRACE"])
                sl = trough - max(2.0, atr * float(c["SL_BUF_ATR"]))
                risk = entry - sl
                if risk > 0:
                    rr = float(c["TP_RR_MAX"]) if c["TRAIL_ENABLED"] else float(c["TP_RR"])
                    tp = entry + risk * rr
                    ok, prob = _ml_ok("BUY", entry)
                    if not ok:
                        return {"signal": "WAIT", "reason": f"blocked by ML ({prob:.2f})"}
                    return _result("BUY", entry, sl, tp,
                                   (f"CHoCH up: close {l_c:.2f} > LH {ref_high:.2f} "
                                    f"after LL {trough:.2f}, disp {body:.2f}/{atr:.2f}ATR"))

    return {"signal": "WAIT", "reason": "No macro structure shift"}
