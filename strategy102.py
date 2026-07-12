# -*- coding: utf-8 -*-
"""
S102: Session Breakout Specialist (อาวุธเสริมของ S101 ในพอร์ต LTS)

แนวคิด (The Alpha):
  S101 เป็น reversal — กินตอนราคา "กลับตัว" ที่จุด liquidity
  S102 กินอีกด้านของเหรียญ: ตอนราคา "ระเบิดออก" จากช่วงสะสมพลัง

  1. Compression Detection — ราคาแกว่งแคบ (range ของ N แท่ง < k×ATR อ้างอิง)
     = ตลาดสะสมพลัง / Asian range ก่อนเซสชันยุโรป-อเมริกา
  2. Breakout Candle — แท่งล่าสุด close ทะลุกรอบ พร้อม body ≥ 1.0×ATR
     และ tick_volume กระชาก ≥ VOL_MULT × ค่าเฉลี่ย (ยืนยันว่ามีเงินจริงดัน)
  3. Session Window — เทรดเฉพาะช่วงเปิด London/NY (ช่วงที่ breakout
     มี follow-through สูงสุด) — ชั่วโมงอ้างอิงเฟรมเดียวกับ dt ใน backtester
  4. Entry LIMIT retrace เข้าขอบกรอบ (breakout แล้วมัก retest) —
     ไม่ไล่ราคาเหมือนสาย breakout ทั่วไปที่โดน fake บ่อย
  5. SL หลังกึ่งกลางกรอบ (ถ้า breakout จริง ราคาไม่ควรกลับเข้าไปลึกเกินครึ่ง)
     TP/Trailing ใช้กลไกเดียวกับ S101 (พิสูจน์แล้วว่า trailing 1.2×ATR ดีสุด)

  ต่างจาก S97 (structure breakout): S102 บังคับ compression + volume spike
  + session window + retest entry — สี่ชั้นที่ตัด false breakout
"""

DEFAULT_CFG = {
    # compression / range
    "RANGE_BARS": 36,          # กรอบสะสมพลัง = N แท่งก่อนแท่ง breakout (36 M5 = 3 ชม.)
    "RANGE_MAX_ATR": 3.0,      # ความกว้างกรอบต้อง < k × ATR(14)
    # breakout candle
    "BREAK_BODY_ATR": 1.0,     # body แท่ง breakout ≥ k × ATR
    "VOL_MULT": 1.0,           # tick_volume ≥ k × avg volume ของกรอบ (sweep: 1.0 ดีสุด — body+session กรองพอแล้ว)
    "CLOSE_OUTSIDE_PCT": 0.3,  # close ต้องพ้นขอบกรอบ ≥ k × ATR
    # session window (ชั่วโมงในเฟรม dt ของ backtester — เฟรมเดียวกับ S96/S99)
    "SESSION_FILTER_ENABLED": True,
    "ALLOW_HOURS": (14, 15, 16, 20, 21, 22),  # London open + NY open
    # entry / risk
    "ENTRY_RETRACE_ATR": 0.15,  # LIMIT ห่างจาก close กลับเข้าหากรอบ k × ATR (retest ตื้น — sweep: 0.15 > 0.3 > 0.5)
    "SL_MODE": "range_mid",    # "range_mid" | "range_opposite"
    "SL_BUF_ATR": 0.3,
    "TP_RR": 1.5,
    # trailing (กลไกเดียวกับ S101)
    "TRAIL_ENABLED": True,
    "TRAIL_BE_RR": 1.0,
    "TRAIL_ATR_MULT": 1.2,
    "TP_RR_MAX": 3.0,
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


def detect_s102(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    rng_bars = int(c["RANGE_BARS"])
    if len(rates) < rng_bars + 20:
        return {"signal": "WAIT", "reason": "Not enough data"}

    if c["SESSION_FILTER_ENABLED"] and dt_bkk is not None:
        if dt_bkk.hour not in c["ALLOW_HOURS"]:
            return {"signal": "WAIT", "reason": f"Outside session window (hour {dt_bkk.hour})"}

    atr = _atr(rates)
    if atr <= 0:
        return {"signal": "WAIT", "reason": "ATR zero"}

    # --- consolidation range: N แท่งก่อนแท่งล่าสุด ---
    box = rates[-rng_bars - 1:-1]
    box_h = max(float(r["high"]) for r in box)
    box_l = min(float(r["low"]) for r in box)
    box_w = box_h - box_l
    if box_w <= 0 or box_w > atr * float(c["RANGE_MAX_ATR"]):
        return {"signal": "WAIT", "reason": f"No compression (range {box_w:.2f})"}
    box_mid = (box_h + box_l) / 2.0

    # --- breakout candle = แท่งล่าสุด ---
    br = rates[-1]
    b_o, b_c = float(br["open"]), float(br["close"])
    b_body = abs(b_c - b_o)
    if b_body < atr * float(c["BREAK_BODY_ATR"]):
        return {"signal": "WAIT", "reason": "Breakout body too small"}

    # volume spike
    avg_vol = sum(float(r["tick_volume"]) for r in box) / len(box)
    if avg_vol > 0 and float(br["tick_volume"]) < avg_vol * float(c["VOL_MULT"]):
        return {"signal": "WAIT", "reason": "No volume spike"}

    out_min = atr * float(c["CLOSE_OUTSIDE_PCT"])

    def _ml_ok(direction, entry):
        if not c["ML_FILTER_ENABLED"]:
            return True, 1.0
        import ml_scoring
        prob = ml_scoring.score_signal('XAUUSD.iux', tf, direction, entry,
                                       dt_bkk, historical_rates=rates)
        return prob >= float(c["ML_SCORE_THRESHOLD"]), prob

    def _result(direction, entry, sl, tp, tags):
        risk = (entry - sl) if direction == "BUY" else (sl - entry)
        res = {
            "signal": direction,
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "order_type": "limit",
            "pattern": f"S102 Session Breakout {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
            "reason": (f"Box {box_l:.2f}-{box_h:.2f} (w={box_w:.2f}), "
                       f"break body {b_body:.2f}, vol x{float(br['tick_volume'])/max(avg_vol,1):.1f}, "
                       f"{tags}"),
            "candles": [br],
        }
        if c["TRAIL_ENABLED"]:
            res["trail"] = {
                "be_rr": float(c["TRAIL_BE_RR"]),
                "atr_mult": float(c["TRAIL_ATR_MULT"]),
                "atr": atr,
                "risk": risk,
            }
        return res

    # ---------- BUY breakout ----------
    if b_c > b_o and b_c >= box_h + out_min:
        entry = b_c - atr * float(c["ENTRY_RETRACE_ATR"])
        entry = max(entry, box_h)  # อย่างลึกสุดแค่ retest ขอบกรอบ
        if c["SL_MODE"] == "range_opposite":
            sl = box_l - max(1.5, atr * float(c["SL_BUF_ATR"]))
        else:
            sl = box_mid - max(1.5, atr * float(c["SL_BUF_ATR"]))
        risk = entry - sl
        if risk <= 0:
            return {"signal": "WAIT", "reason": "Invalid risk"}
        rr = float(c["TP_RR_MAX"]) if c["TRAIL_ENABLED"] else float(c["TP_RR"])
        tp = entry + risk * rr
        ok, prob = _ml_ok("BUY", entry)
        if not ok:
            return {"signal": "WAIT", "reason": f"S102 BUY blocked by ML ({prob:.2f})"}
        return _result("BUY", entry, sl, tp, "retest-limit above box")

    # ---------- SELL breakout ----------
    if b_c < b_o and b_c <= box_l - out_min:
        entry = b_c + atr * float(c["ENTRY_RETRACE_ATR"])
        entry = min(entry, box_l)
        if c["SL_MODE"] == "range_opposite":
            sl = box_h + max(1.5, atr * float(c["SL_BUF_ATR"]))
        else:
            sl = box_mid + max(1.5, atr * float(c["SL_BUF_ATR"]))
        risk = sl - entry
        if risk <= 0:
            return {"signal": "WAIT", "reason": "Invalid risk"}
        rr = float(c["TP_RR_MAX"]) if c["TRAIL_ENABLED"] else float(c["TP_RR"])
        tp = entry - risk * rr
        ok, prob = _ml_ok("SELL", entry)
        if not ok:
            return {"signal": "WAIT", "reason": f"S102 SELL blocked by ML ({prob:.2f})"}
        return _result("SELL", entry, sl, tp, "retest-limit below box")

    return {"signal": "WAIT", "reason": "No breakout from compression"}
