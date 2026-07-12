# -*- coding: utf-8 -*-
"""
S106: The Judas Swing — Killzone Fakeout Fade (Asian Range Stop Hunt)

ทำไมไม่แย่งออเดอร์กับ S99-S105:
  S102 เทรด breakout ที่ "สำเร็จ" (volume หนุน + ไปต่อ)
  S106 เทรด breakout ที่ "ล้มเหลว" — ราคาทะลุ High/Low ของ Asian range
  ช่วง killzone (London/NY open) เพื่อกวาด stop แล้ว "ชักกลับเข้ากรอบ"
  → เงื่อนไขของสองตัวนี้ exclusive กันโดยนิยาม (แท่งเดียวกันเป็นได้อย่างเดียว)
  S105 มองแท่ง spike 3xATR เดี่ยวๆ / S106 มอง "ระดับราคาอ้างอิงเชิงเซสชัน"
  ไม่ต้องมี spike ก็เกิด Judas ได้

ตรรกะ (The Alpha — ICT Judas Swing):
  1. Asian Range — High/Low ของช่วงเอเชีย (ชั่วโมง ASIA ในเฟรมเวลาของ backtester)
     กรอบต้องกว้างพอมีนัย (>= MIN_RANGE_ATR) และไม่กว้างเกิน (<= MAX_RANGE_ATR)
  2. Judas Break — ระหว่าง killzone ราคา "ทะลุ" ขอบกรอบด้วยความลึกอย่างน้อย
     MIN_BREAK_ATR (ของปลอมต้องลึกพอที่จะกวาด stop จริง)
  3. Re-entry Trigger — แท่งล่าสุด "close กลับเข้ากรอบ" เป็นแท่งแรก
     (แท่งก่อนหน้ายัง close อยู่นอกกรอบ) = จังหวะ trap ปิดตัว
  4. Fade — เข้า market สวนทันที (sim จะ fill ที่ open แท่งถัดไปตามกฎ Reality Check)
     SL หลังปลาย fakeout + buffer / TP ที่ "ขอบตรงข้าม" ของ Asian range
     (liquidity เป้าหมายถัดไปของ smart money หลังกวาดฝั่งแรกเสร็จ)
  5. หนึ่ง setup ต่อวันต่อฝั่ง (แท่ง trigger แรกเท่านั้น — กันยิงรัว)

กฎเหล็ก Reality Check: ใช้เฉพาะแท่งที่ปิดแล้ว, ไม่มี look-ahead,
sim ใช้ SL-first + spread penetration + market = next open
"""

DEFAULT_CFG = {
    # ชั่วโมงในเฟรม dt ของ backtester (เฟรมเดียวกับ S96/S99/S102)
    "ASIA_HOURS": (7, 8, 9, 10, 11, 12, 13),   # ช่วงสร้าง Asian range
    "KILLZONE_HOURS": (14, 15, 16, 20, 21, 22),  # London + NY open — ล่า Judas
    "MIN_RANGE_ATR": 1.5,      # กรอบเอเชียต้องกว้าง >= k×ATR
    "MAX_RANGE_ATR": 8.0,      # และไม่กว้างเกิน (วันเทรนด์จัดตั้งแต่เช้า)
    "MIN_BREAK_ATR": 0.8,      # ความลึกของ fakeout เกินขอบ >= k×ATR (sweep: 0.8 > 0.5 > 0.3)
    "MAX_BREAK_ATR": 2.0,      # ลึกเกินนี้ = breakout จริง ไม่ใช่ Judas — ไม่สวน (sweep: 2.0 ชนะ 1.5/2.5/3.0 ชัด)
    "SL_BUF_ATR": 0.3,         # SL หลังปลาย fakeout + k×ATR
    "TP_TARGET": "opposite",   # "opposite" = ขอบตรงข้าม / "mid" = กลางกรอบ / "rr"
    "TP_RR": 1.5,              # ใช้เมื่อ TP_TARGET = "rr"
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


def detect_s106(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    from datetime import datetime as _dt

    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    if len(rates) < 120 or dt_bkk is None:
        return {"signal": "WAIT", "reason": "Not enough data / no time"}

    if dt_bkk.hour not in c["KILLZONE_HOURS"]:
        return {"signal": "WAIT", "reason": f"Outside killzone (hour {dt_bkk.hour})"}

    atr = _atr(rates)
    if atr <= 0:
        return {"signal": "WAIT", "reason": "ATR zero"}

    cur_date = dt_bkk.date()
    asia_hours = set(c["ASIA_HOURS"])

    # --- Asian range ของ "วันนี้" (เฉพาะแท่งที่ปิดแล้ว) ---
    asia_h, asia_l = None, None
    post_asia = []   # แท่งหลังจบช่วงเอเชียของวันนี้ (รวมแท่งล่าสุด)
    for r in rates:
        d = _dt.fromtimestamp(int(r["time"]))
        if d.date() != cur_date:
            continue
        if d.hour in asia_hours:
            h, l = float(r["high"]), float(r["low"])
            asia_h = h if asia_h is None else max(asia_h, h)
            asia_l = l if asia_l is None else min(asia_l, l)
        elif d.hour > max(asia_hours):
            post_asia.append(r)

    if asia_h is None or asia_l is None:
        return {"signal": "WAIT", "reason": "No Asian range today"}
    rng = asia_h - asia_l
    if rng < atr * float(c["MIN_RANGE_ATR"]):
        return {"signal": "WAIT", "reason": "Asian range too narrow"}
    if rng > atr * float(c["MAX_RANGE_ATR"]):
        return {"signal": "WAIT", "reason": "Asian range too wide (trend day)"}
    if len(post_asia) < 2:
        return {"signal": "WAIT", "reason": "Killzone just started"}

    last, prev = post_asia[-1], post_asia[-2]
    l_c = float(last["close"])
    p_c = float(prev["close"])
    mid = (asia_h + asia_l) / 2.0
    min_break = atr * float(c["MIN_BREAK_ATR"])
    max_break = atr * float(c["MAX_BREAK_ATR"])

    def _ml_ok(direction, entry):
        if not c["ML_FILTER_ENABLED"]:
            return True, 1.0
        import ml_scoring
        prob = ml_scoring.score_signal('XAUUSD.iux', tf, direction, entry,
                                       dt_bkk, historical_rates=rates)
        return prob >= float(c["ML_SCORE_THRESHOLD"]), prob

    def _result(direction, entry, sl, tp, why):
        return {
            "signal": direction,
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "order_type": "market",
            "pattern": f"S106 Judas Swing {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
            "reason": why,
            "candles": [last],
        }

    # ---------- SELL: Judas ทะลุขึ้นเหนือ Asian High แล้วชักกลับ ----------
    # fakeout สูงสุดหลังช่วงเอเชีย
    fake_hi = max(float(r["high"]) for r in post_asia)
    if fake_hi >= asia_h + min_break and (fake_hi - asia_h) <= max_break:
        # trigger แท่งแรกที่ close กลับเข้ากรอบ (แท่งก่อนหน้ายังอยู่นอก)
        if l_c < asia_h and p_c >= asia_h:
            sl = fake_hi + max(1.5, atr * float(c["SL_BUF_ATR"]))
            if c["TP_TARGET"] == "mid":
                tp = mid
            elif c["TP_TARGET"] == "rr":
                tp = l_c - (sl - l_c) * float(c["TP_RR"])
            else:
                tp = asia_l
            if sl - l_c > 0 and l_c - tp > 0:
                ok, prob = _ml_ok("SELL", l_c)
                if not ok:
                    return {"signal": "WAIT", "reason": f"blocked by ML ({prob:.2f})"}
                return _result("SELL", l_c, sl, tp,
                               (f"Judas above Asian high {asia_h:.2f} "
                                f"(fake {fake_hi:.2f}, depth {(fake_hi-asia_h)/atr:.1f}ATR) "
                                f"re-entered"))

    # ---------- BUY: Judas ทะลุลงใต้ Asian Low แล้วชักกลับ ----------
    fake_lo = min(float(r["low"]) for r in post_asia)
    if fake_lo <= asia_l - min_break and (asia_l - fake_lo) <= max_break:
        if l_c > asia_l and p_c <= asia_l:
            sl = fake_lo - max(1.5, atr * float(c["SL_BUF_ATR"]))
            if c["TP_TARGET"] == "mid":
                tp = mid
            elif c["TP_TARGET"] == "rr":
                tp = l_c + (l_c - sl) * float(c["TP_RR"])
            else:
                tp = asia_h
            if l_c - sl > 0 and tp - l_c > 0:
                ok, prob = _ml_ok("BUY", l_c)
                if not ok:
                    return {"signal": "WAIT", "reason": f"blocked by ML ({prob:.2f})"}
                return _result("BUY", l_c, sl, tp,
                               (f"Judas below Asian low {asia_l:.2f} "
                                f"(fake {fake_lo:.2f}, depth {(asia_l-fake_lo)/atr:.1f}ATR) "
                                f"re-entered"))

    return {"signal": "WAIT", "reason": "No Judas swing setup"}
