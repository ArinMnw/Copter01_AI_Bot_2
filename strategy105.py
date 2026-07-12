# -*- coding: utf-8 -*-
"""
S105: Volatility Anomaly Fade — The Anomaly Hunter (ไพ่ตายนอกตำรา)

ทำไมไม่ซ้ำกับ 6 ตัวแรก:
  S99-S104 ทั้งหมดอ่าน "โครงสร้าง" (swing/box/VWAP/CHoCH) และส่วนใหญ่
  มี filter หลบช่วงผันผวนรุนแรง — วินาทีที่ข่าว CPI/NFP/FOMC กระชาก
  คือจุดบอดร่วมของทั้งตระกูล
  S105 ทำงาน "เฉพาะ" ตอนนั้น: แท่งกระชากผิดปกติ (>= 3xATR) คือ anomaly
  เชิงสถิติที่มัก overshoot แล้วดีดกลับ เมื่อเห็นอาการชะงัก (rejection)

ตรรกะ (The Alpha):
  1. Anomaly Detection — range ของแท่ง spike >= SPIKE_ATR x ATR อ้างอิง
     (ATR คำนวณ "ก่อน" แท่ง spike — ไม่ให้ spike ปนเปื้อนตัววัดของตัวเอง)
  2. Rejection สองแบบ (Pattern A/B):
     A. Same-bar pinbar — แท่ง spike เองทิ้ง wick ยาวสวนทาง (close ดีดกลับแล้ว)
     B. Next-bar stall — แท่ง spike ปิดสุดโต่ง แล้วแท่งถัดมา "ชะงัก"
        (body เล็ก หรือปิดสวนทาง spike)
  3. Fade — เข้าสวนทิศ spike ด้วย market ที่ close
     SL หลังปลาย spike + buffer / TP = ดีดกลับ k% ของ range spike
     (เป้าธรรมชาติของ overshoot คือถอยกลับเข้าหาจุดเริ่ม ไม่ใช่ let-run)
  4. ไม่มี structure filter, ไม่มี trend filter — anomaly คือ signal ในตัวเอง
     มี guard เดียว: spike ต้องไม่ใช่แท่งที่ 2-3 ของ cascade (ข่าวใหญ่ที่วิ่งต่อ)
     → เช็คว่าก่อนแท่ง spike ตลาดยัง "ปกติ" (แท่งก่อนหน้า < NORMAL_ATR x ATR)
"""

DEFAULT_CFG = {
    "SPIKE_ATR": 3.0,          # range แท่ง spike >= k × ATR อ้างอิง
    "ATR_PERIOD": 14,
    "NORMAL_ATR": 1.5,         # แท่งก่อน spike ต้อง range < k×ATR (กัน cascade)
    "PATTERN_A": False,        # same-bar pinbar fade (sweep: แพ้ B ชัด — default off)
    "PATTERN_B": True,         # next-bar stall fade (แกนหลักของ edge)
    # Pattern A: pinbar บนแท่ง spike เอง
    "A_WICK_PCT": 0.40,        # wick สวนทาง >= 40% ของ range แท่ง spike
    # Pattern B: แท่งถัดจาก spike ชะงัก
    "B_STALL_BODY_ATR": 0.5,   # body แท่ง stall <= k×ATR (ชะงัก) หรือปิดสวนทาง
    # entry
    "ENTRY_MODE": "retrace",   # "market" = เข้าที่ close / "retrace" = limit ลึกเข้าหาปลาย spike
    "ENTRY_RETRACE_PCT": 0.45,  # limit ลึก 45% ของ range (sweep: 0.45 → PF 3.05, market → PF 1.11)
    # risk
    "SL_BUF_ATR": 0.3,         # SL หลังปลาย spike + k×ATR
    "TP_SPIKE_PCT": 0.5,       # TP = ดีดกลับ k ของ range spike (วัดจาก entry ไปทาง fade)
    "MIN_RISK_ATR": 0.5,       # ความเสี่ยงขั้นต่ำ (กัน entry ชิดปลาย spike เกิน)
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


def detect_s105(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    period = int(c["ATR_PERIOD"])
    if len(rates) < period + 10:
        return {"signal": "WAIT", "reason": "Not enough data"}

    def _ml_ok(direction, entry):
        if not c["ML_FILTER_ENABLED"]:
            return True, 1.0
        import ml_scoring
        prob = ml_scoring.score_signal('XAUUSD.iux', tf, direction, entry,
                                       dt_bkk, historical_rates=rates)
        return prob >= float(c["ML_SCORE_THRESHOLD"]), prob

    def _result(direction, entry, sl, tp, pattern_tag, why):
        return {
            "signal": direction,
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "order_type": "market" if c["ENTRY_MODE"] == "market" else "limit",
            "pattern": f"S105 Anomaly Fade {pattern_tag} "
                       f"{'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
            "reason": why,
            "candles": [rates[-1]],
        }

    def _build(direction, spike_h, spike_l, spike_range, entry, tag, why):
        atr_ref_local = spike_range / float(c["SPIKE_ATR"])
        if c["ENTRY_MODE"] == "retrace":
            # limit ลึกเข้าหาปลาย spike — รอตลาดเด้งกลับมาให้ราคาดีกว่า
            if direction == "SELL":
                entry = entry + spike_range * float(c["ENTRY_RETRACE_PCT"])
                entry = min(entry, spike_h)
            else:
                entry = entry - spike_range * float(c["ENTRY_RETRACE_PCT"])
                entry = max(entry, spike_l)
        if direction == "SELL":
            sl = spike_h + max(1.5, atr_ref_local * float(c["SL_BUF_ATR"]))
            tp = entry - spike_range * float(c["TP_SPIKE_PCT"])
            if sl - entry < atr_ref_local * float(c["MIN_RISK_ATR"]):
                return None
            if entry - tp <= 0:
                return None
        else:
            sl = spike_l - max(1.5, atr_ref_local * float(c["SL_BUF_ATR"]))
            tp = entry + spike_range * float(c["TP_SPIKE_PCT"])
            if entry - sl < atr_ref_local * float(c["MIN_RISK_ATR"]):
                return None
            if tp - entry <= 0:
                return None
        ok, prob = _ml_ok(direction, entry)
        if not ok:
            return {"signal": "WAIT", "reason": f"blocked by ML ({prob:.2f})"}
        return _result(direction, entry, sl, tp, tag, why)

    # ---------- Pattern A: แท่งล่าสุดคือ spike + pinbar ในตัว ----------
    if c["PATTERN_A"]:
        sp = rates[-1]
        sp_h, sp_l = float(sp["high"]), float(sp["low"])
        sp_o, sp_c = float(sp["open"]), float(sp["close"])
        sp_range = sp_h - sp_l
        # ATR อ้างอิงจากแท่งก่อนหน้า spike
        atr_ref = _atr(rates[:-1], period)
        if atr_ref > 0 and sp_range >= atr_ref * float(c["SPIKE_ATR"]):
            prev = rates[-2]
            prev_range = float(prev["high"]) - float(prev["low"])
            if prev_range < atr_ref * float(c["NORMAL_ATR"]):  # ก่อนหน้ายังปกติ
                upper_wick = sp_h - max(sp_o, sp_c)
                lower_wick = min(sp_o, sp_c) - sp_l
                # spike ขึ้น + wick บนยาว = โดนขายกลับ → SELL
                if upper_wick >= sp_range * float(c["A_WICK_PCT"]) and \
                        (sp_h - float(prev["high"])) > atr_ref:  # spike ไปทางขึ้น
                    r = _build("SELL", sp_h, sp_l, sp_range, sp_c, "A",
                               (f"Spike up {sp_range:.2f} ({sp_range/atr_ref:.1f}xATR) "
                                f"rejected: upper wick {upper_wick/sp_range*100:.0f}%"))
                    if r:
                        return r
                if lower_wick >= sp_range * float(c["A_WICK_PCT"]) and \
                        (float(prev["low"]) - sp_l) > atr_ref:  # spike ไปทางลง
                    r = _build("BUY", sp_h, sp_l, sp_range, sp_c, "A",
                               (f"Spike down {sp_range:.2f} ({sp_range/atr_ref:.1f}xATR) "
                                f"rejected: lower wick {lower_wick/sp_range*100:.0f}%"))
                    if r:
                        return r

    # ---------- Pattern B: แท่ง [-2] คือ spike, แท่ง [-1] ชะงัก ----------
    if c["PATTERN_B"]:
        sp = rates[-2]
        st = rates[-1]
        sp_h, sp_l = float(sp["high"]), float(sp["low"])
        sp_o, sp_c = float(sp["open"]), float(sp["close"])
        sp_range = sp_h - sp_l
        atr_ref = _atr(rates[:-2], period)
        if atr_ref > 0 and sp_range >= atr_ref * float(c["SPIKE_ATR"]):
            prev = rates[-3]
            prev_range = float(prev["high"]) - float(prev["low"])
            if prev_range < atr_ref * float(c["NORMAL_ATR"]):
                st_o, st_c = float(st["open"]), float(st["close"])
                st_body = abs(st_c - st_o)
                spike_up = sp_c > sp_o
                stalled = st_body <= atr_ref * float(c["B_STALL_BODY_ATR"]) or \
                          (spike_up and st_c < st_o) or (not spike_up and st_c > st_o)
                if stalled:
                    if spike_up:
                        r = _build("SELL", max(sp_h, float(st["high"])), sp_l,
                                   sp_range, st_c, "B",
                                   (f"Spike up {sp_range/atr_ref:.1f}xATR then stall "
                                    f"(body {st_body:.2f})"))
                        if r:
                            return r
                    else:
                        r = _build("BUY", sp_h, min(sp_l, float(st["low"])),
                                   sp_range, st_c, "B",
                                   (f"Spike down {sp_range/atr_ref:.1f}xATR then stall "
                                    f"(body {st_body:.2f})"))
                        if r:
                            return r

    return {"signal": "WAIT", "reason": "No volatility anomaly"}
