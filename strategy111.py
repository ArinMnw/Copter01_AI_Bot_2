# -*- coding: utf-8 -*-
"""
S111: The Fundamental Gap Magnet — Weekend Gap Fill + Mega Imbalance Void

ทำไมมิตินี้ยังว่างอยู่:
  ทั้ง 10 ตัวแรกอ่าน "พฤติกรรมราคาใน session ปกติ" — ไม่มีตัวไหนแตะ
  "รอยขาด" ของราคา: gap เสาร์-อาทิตย์ (ตลาดปิดแต่โลกไม่หยุดหมุน) และ
  mega-FVG จากข่าวแรง (imbalance สุดโต่งที่ไม่มีการจับคู่ซื้อขาย)
  สถิติที่รู้กันในตลาดทอง: gap ขนาดกลางมีแรงดึงดูดกลับ (magnet) สูง
  เพราะ market maker ต้องการปิด imbalance

สองโหมด:
  A. WEEKEND — แท่งแรกหลังตลาดปิดยาว (ช่องเวลาระหว่างแท่ง >= GAP_MIN_HOURS)
     เปิดห่างจาก close ก่อนปิด >= GAP_MIN_ATR×ATR และยังไม่ถูกเติม
     → เข้า "fade" ทิศกลับหา close เดิม (market ที่แท่งถัดไป)
     TP = เติม gap เต็ม (close ก่อนปิด) / SL = เลย extreme ฝั่ง gap + buffer
     กติกา: gap ใหญ่เกิน GAP_MAX_ATR ไม่เล่น (ข่าวเปลี่ยนโลก — อย่าขวาง)
  B. VOID — mega-FVG 3 แท่ง (void >= VOID_MIN_ATR×ATR) ที่ยังไม่ถูกเติม
     → ตั้ง LIMIT ที่ "ก้น" ของ void (ขอบไกล = จุดเติมสมบูรณ์)
     รอราคาย้อนกลับมาเติมแล้วเด้ง: TP = ขอบใกล้ของ void / SL = เลยก้น + buffer

กฎเหล็ก Reality Check: ใช้แท่งปิดแล้ว, limit fill ต้องทะลุ spread, SL-first (sim),
market เข้าที่ open แท่งถัดไป (sim)
"""

DEFAULT_CFG = {
    "MODE_WEEKEND": False,  # falsified: fade weekend gap ทองยุคเทรนด์ = PF 0.19-0.47 ทุก config
    "MODE_VOID": True,
    # weekend gap
    "GAP_MIN_HOURS": 24.0,     # ช่องเวลาระหว่างแท่ง >= ชม. = ตลาดปิดยาว
    "GAP_MIN_ATR": 1.0,        # ขนาด gap ขั้นต่ำ (x ATR)
    "GAP_MAX_ATR": 8.0,        # ใหญ่เกินนี้ไม่ fade
    "GAP_MAX_AGE": 36,         # แท่งหลัง gap ที่ยังยอมเข้า (fade ต้องทำเร็ว)
    "GAP_SL_ATR": 1.5,         # SL เลย extreme ฝั่ง gap + k×ATR
    # mega void (FVG สุดโต่ง)
    "VOID_MIN_ATR": 3.0,       # ขนาด void ขั้นต่ำ (x ATR) — sweep: 3.0 ดีสุด (PF 2.2-2.6)
    "VOID_SCAN_BARS": 120,     # ค้น void ย้อนหลังกี่แท่ง
    "VOID_MAX_AGE": 100,       # อายุ void สูงสุด
    "VOID_SL_ATR": 0.5,        # SL เลยก้น void + k×ATR
    "VOID_TP_PCT": 1.0,        # TP = เด้งกลับ k ของความสูง void (1.0 = ขอบใกล้)
    "TIME_FILTER_ENABLED": False,   # gap ไม่เลือกเวลา
    "BLOCK_HOURS": (),
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


def detect_s111(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    if len(rates) < 140:
        return {"signal": "WAIT", "reason": "Not enough data"}

    if c["TIME_FILTER_ENABLED"] and dt_bkk is not None:
        if dt_bkk.hour in c["BLOCK_HOURS"]:
            return {"signal": "WAIT", "reason": f"Blocked hour {dt_bkk.hour}"}

    atr = _atr(rates)
    if atr <= 0:
        return {"signal": "WAIT", "reason": "ATR zero"}

    n = len(rates)
    last_close = float(rates[-1]["close"])

    def _result(direction, entry, sl, tp, order_type, tag, why):
        return {
            "signal": direction,
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "order_type": order_type,
            "pattern": f"S111 Gap Magnet [{tag}] "
                       f"{'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
            "reason": why,
            "candles": [rates[-1]],
        }

    # ---------- Mode A: Weekend / long-close gap ----------
    if c["MODE_WEEKEND"]:
        gap_secs = float(c["GAP_MIN_HOURS"]) * 3600.0
        # หา gap ล่าสุดภายใน GAP_MAX_AGE แท่ง
        lo_i = max(1, n - int(c["GAP_MAX_AGE"]))
        for i in range(n - 1, lo_i - 1, -1):
            dt_gap = int(rates[i]["time"]) - int(rates[i - 1]["time"])
            if dt_gap < gap_secs:
                continue
            prev_close = float(rates[i - 1]["close"])
            open_px = float(rates[i]["open"])
            gap = open_px - prev_close
            if abs(gap) < atr * float(c["GAP_MIN_ATR"]) or \
               abs(gap) > atr * float(c["GAP_MAX_ATR"]):
                break  # gap ล่าสุดไม่เข้าเกณฑ์ — ไม่มองย้อนไปอีก
            # เติมแล้วหรือยัง (นับจากแท่ง gap ถึงปัจจุบัน)
            if gap > 0:
                filled = any(float(rates[j]["low"]) <= prev_close for j in range(i, n))
            else:
                filled = any(float(rates[j]["high"]) >= prev_close for j in range(i, n))
            if filled:
                break
            # fade ทิศกลับหา prev_close
            if gap > 0:
                extreme = max(float(rates[j]["high"]) for j in range(i, n))
                sl = extreme + max(1.5, atr * float(c["GAP_SL_ATR"]))
                tp = prev_close
                if last_close - tp > 0 and sl - last_close > 0:
                    return _result("SELL", last_close, sl, tp, "market", "WKND",
                                   (f"Gap up {gap:.2f} ({gap/atr:.1f}ATR) unfilled, "
                                    f"fade to {prev_close:.2f}"))
            else:
                extreme = min(float(rates[j]["low"]) for j in range(i, n))
                sl = extreme - max(1.5, atr * float(c["GAP_SL_ATR"]))
                tp = prev_close
                if tp - last_close > 0 and last_close - sl > 0:
                    return _result("BUY", last_close, sl, tp, "market", "WKND",
                                   (f"Gap down {gap:.2f} ({abs(gap)/atr:.1f}ATR) unfilled, "
                                    f"fade to {prev_close:.2f}"))
            break

    # ---------- Mode B: Mega imbalance void (FVG สุดโต่ง) ----------
    if c["MODE_VOID"]:
        scan_lo = max(2, n - int(c["VOID_SCAN_BARS"]))
        best = None
        for i in range(n - 2, scan_lo, -1):
            a, b_, c_ = rates[i - 1], rates[i], rates[i + 1]
            a_h, a_l = float(a["high"]), float(a["low"])
            c_h, c_l = float(c_["high"]), float(c_["low"])
            # bullish void: low(c) > high(a)
            if c_l - a_h >= atr * float(c["VOID_MIN_ATR"]):
                vb, vt, direction = a_h, c_l, "BUY"
            # bearish void: high(c) < low(a)
            elif a_l - c_h >= atr * float(c["VOID_MIN_ATR"]):
                vb, vt, direction = c_h, a_l, "SELL"
            else:
                continue
            if (n - 1) - i > int(c["VOID_MAX_AGE"]):
                break
            # ยังไม่ถูกเติมเต็ม (ราคายังไม่แตะ "ก้น" void = ขอบไกล)
            if direction == "BUY":
                touched = any(float(rates[j]["low"]) <= vb for j in range(i + 2, n))
                if touched or last_close <= vb:
                    continue
                entry = vb
                sl = vb - max(1.5, atr * float(c["VOID_SL_ATR"]))
                tp = vb + (vt - vb) * float(c["VOID_TP_PCT"])
            else:
                touched = any(float(rates[j]["high"]) >= vt for j in range(i + 2, n))
                if touched or last_close >= vt:
                    continue
                entry = vt
                sl = vt + max(1.5, atr * float(c["VOID_SL_ATR"]))
                tp = vt - (vt - vb) * float(c["VOID_TP_PCT"])
            best = (direction, entry, sl, tp, vt - vb, (n - 1) - i)
            break
        if best:
            direction, entry, sl, tp, vsize, age = best
            return _result(direction, entry, sl, tp, "limit", "VOID",
                           (f"Mega void {vsize:.2f} ({vsize/atr:.1f}ATR, age {age}) "
                            f"limit at deep edge {entry:.2f}"))

    return {"signal": "WAIT", "reason": "No unfilled gap / mega void"}
