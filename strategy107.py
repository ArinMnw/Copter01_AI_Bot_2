# -*- coding: utf-8 -*-
"""
S107: The Unmitigated Origin — Order Block First Mitigation (S&D Deep Base)

ทำไมไม่แย่งออเดอร์กับ S99-S106:
  ทั้ง 8 ตัวแรกเทรด "เหตุการณ์ที่เพิ่งเกิด" — sweep สดๆ (S99-S101), breakout สดๆ
  (S102), spike สดๆ (S105), fakeout สดๆ (S106)
  S107 กลับด้านมิติเวลา: ระบุ "จุดกำเนิดของ impulse" (Origin Order Block)
  แล้วตั้ง LIMIT ดักรอราคา "กลับมาเยือนครั้งแรก" ซึ่งอาจเกิดอีกหลายชั่วโมงถัดมา
  → ช่วงเวลาถือ pending และจังหวะ fill ไม่ overlap กับใครเลย

ตรรกะ (The Alpha — Supply & Demand Mitigation):
  1. BOS (Break of Structure) — แท่งล่าสุด close ทะลุ swing high/low (pivot 3/3)
     พร้อม displacement แรง (body >= k×ATR) = impulse ที่สถาบันผลักจริง
  2. Origin OB — แท่งสีตรงข้าม "แท่งสุดท้าย" ก่อน impulse เริ่ม
     (แท่งที่สถาบันเก็บออเดอร์ก่อนผลัก) โซน = high..low ของแท่งนั้น
  3. Unmitigated — ตั้งแต่ OB เกิดจนถึงปัจจุบัน ราคาห้ามเคยย้อนแตะโซนเลย
     (first mitigation เท่านั้น — การแตะครั้งแรกคือครั้งที่ order เหลือเยอะสุด)
  4. Entry — LIMIT ที่ "ขอบบนของโซน" (BUY) / ขอบล่าง (SELL) + entry ลึกได้ผ่าน
     OB_ENTRY_DEPTH (0 = ขอบโซน, 0.5 = กลางโซน)
  5. SL หลังปลายโซน + buffer / TP = RR คงที่ (โครงสร้างถัดไปมัก >= 2R)
  6. Fresh window — สัญญาณออกเฉพาะตอน BOS เพิ่งยืนยัน (กัน emit ซ้ำ)
     ฝั่ง sim ให้ pending รอได้นาน (fill window ยาว) ตามธรรมชาติของ mitigation

กฎเหล็ก Reality Check: ใช้แท่งปิดแล้วเท่านั้น + sim SL-first + limit fill ทะลุ spread
"""

DEFAULT_CFG = {
    "SWING_LEFT": 3,
    "SWING_RIGHT": 3,
    "SWING_SCAN_BARS": 80,
    "BOS_DISP_ATR": 1.8,       # body แท่ง BOS >= k×ATR (sweep: 1.8 ดีสุด — impulse ต้องแรงจริง, 2.2 น้อยเกิน)
    "BOS_CLOSE_BEYOND_ATR": 0.2,  # close ต้องพ้น swing >= k×ATR
    "OB_SEARCH_BARS": 10,      # ค้นแท่งสีตรงข้ามย้อนหลังจากแท่ง BOS ไม่เกิน N แท่ง
    "OB_MAX_SIZE_ATR": 2.5,    # โซน OB ต้องไม่ใหญ่เกิน (ใหญ่ไป = ไม่ใช่ base)
    "OB_ENTRY_DEPTH": 0.0,     # 0 = ขอบโซน / 0.5 = กลางโซน
    "SL_BUF_ATR": 0.3,
    "TP_RR": 2.0,
    "PD_FILTER_ENABLED": True,  # BUY OB ต้องอยู่ discount / SELL อยู่ premium
    "PD_RANGE_BARS": 150,
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


def detect_s107(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    if len(rates) < 160:
        return {"signal": "WAIT", "reason": "Not enough data"}

    if c["TIME_FILTER_ENABLED"] and dt_bkk is not None:
        if dt_bkk.hour in c["BLOCK_HOURS"]:
            return {"signal": "WAIT", "reason": f"Blocked hour {dt_bkk.hour}"}

    atr = _atr(rates)
    if atr <= 0:
        return {"signal": "WAIT", "reason": "ATR zero"}

    n = len(rates)
    bos = rates[-1]
    b_o, b_c = float(bos["open"]), float(bos["close"])
    b_body = abs(b_c - b_o)
    if b_body < atr * float(c["BOS_DISP_ATR"]):
        return {"signal": "WAIT", "reason": "No displacement"}

    sw_highs, sw_lows = _find_swings(
        rates, int(c["SWING_LEFT"]), int(c["SWING_RIGHT"]), int(c["SWING_SCAN_BARS"]))
    if not sw_highs or not sw_lows:
        return {"signal": "WAIT", "reason": "Structure not mapped"}

    beyond = atr * float(c["BOS_CLOSE_BEYOND_ATR"])

    pd_bars = rates[-int(c["PD_RANGE_BARS"]):]
    rng_h = max(float(r["high"]) for r in pd_bars)
    rng_l = min(float(r["low"]) for r in pd_bars)
    eq = (rng_h + rng_l) / 2.0

    def _ml_ok(direction, entry):
        if not c["ML_FILTER_ENABLED"]:
            return True, 1.0
        import ml_scoring
        prob = ml_scoring.score_signal('XAUUSD.iux', tf, direction, entry,
                                       dt_bkk, historical_rates=rates)
        return prob >= float(c["ML_SCORE_THRESHOLD"]), prob

    def _result(direction, entry, sl, tp, ob_idx, ob_top, ob_bot, ref):
        return {
            "signal": direction,
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "order_type": "limit",
            "pattern": f"S107 Origin OB {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
            "reason": (f"BOS beyond {ref:.2f} (body {b_body/atr:.1f}ATR), "
                       f"unmitigated OB[{n-1-ob_idx} bars ago] "
                       f"{ob_bot:.2f}-{ob_top:.2f}"),
            "candles": [rates[ob_idx], bos],
        }

    # ---------- BUY: BOS ขึ้นทะลุ swing high → Demand OB ----------
    last_sw_high = sw_highs[-1][1]
    if b_c > b_o and b_c >= last_sw_high + beyond:
        # หาแท่งแดงสุดท้ายก่อน impulse (ย้อนจากแท่ง BOS)
        ob_idx = None
        for k in range(n - 2, max(n - 2 - int(c["OB_SEARCH_BARS"]), 0), -1):
            r = rates[k]
            if float(r["close"]) < float(r["open"]):
                ob_idx = k
                break
        if ob_idx is not None:
            ob_top = float(rates[ob_idx]["high"])
            ob_bot = float(rates[ob_idx]["low"])
            zone_size = ob_top - ob_bot
            if 0 < zone_size <= atr * float(c["OB_MAX_SIZE_ATR"]):
                # unmitigated: หลัง OB (ไม่นับแท่ง OB กับแท่งถัดไปที่เป็นขา impulse)
                mitigated = any(float(rates[j]["low"]) <= ob_top
                                for j in range(ob_idx + 2, n - 1))
                if not mitigated:
                    if c["PD_FILTER_ENABLED"] and ob_top > eq:
                        return {"signal": "WAIT", "reason": "Demand OB not in discount"}
                    entry = ob_top - zone_size * float(c["OB_ENTRY_DEPTH"])
                    sl = ob_bot - max(1.5, atr * float(c["SL_BUF_ATR"]))
                    risk = entry - sl
                    if risk > 0:
                        tp = entry + risk * float(c["TP_RR"])
                        ok, prob = _ml_ok("BUY", entry)
                        if not ok:
                            return {"signal": "WAIT", "reason": f"blocked by ML ({prob:.2f})"}
                        return _result("BUY", entry, sl, tp, ob_idx, ob_top, ob_bot,
                                       last_sw_high)

    # ---------- SELL: BOS ลงทะลุ swing low → Supply OB ----------
    last_sw_low = sw_lows[-1][1]
    if b_c < b_o and b_c <= last_sw_low - beyond:
        ob_idx = None
        for k in range(n - 2, max(n - 2 - int(c["OB_SEARCH_BARS"]), 0), -1):
            r = rates[k]
            if float(r["close"]) > float(r["open"]):
                ob_idx = k
                break
        if ob_idx is not None:
            ob_top = float(rates[ob_idx]["high"])
            ob_bot = float(rates[ob_idx]["low"])
            zone_size = ob_top - ob_bot
            if 0 < zone_size <= atr * float(c["OB_MAX_SIZE_ATR"]):
                mitigated = any(float(rates[j]["high"]) >= ob_bot
                                for j in range(ob_idx + 2, n - 1))
                if not mitigated:
                    if c["PD_FILTER_ENABLED"] and ob_bot < eq:
                        return {"signal": "WAIT", "reason": "Supply OB not in premium"}
                    entry = ob_bot + zone_size * float(c["OB_ENTRY_DEPTH"])
                    sl = ob_top + max(1.5, atr * float(c["SL_BUF_ATR"]))
                    risk = sl - entry
                    if risk > 0:
                        tp = entry - risk * float(c["TP_RR"])
                        ok, prob = _ml_ok("SELL", entry)
                        if not ok:
                            return {"signal": "WAIT", "reason": f"blocked by ML ({prob:.2f})"}
                        return _result("SELL", entry, sl, tp, ob_idx, ob_top, ob_bot,
                                       last_sw_low)

    return {"signal": "WAIT", "reason": "No BOS + unmitigated origin OB"}
