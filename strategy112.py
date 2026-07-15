# -*- coding: utf-8 -*-
"""
S112: SMC Liquidity Sniper (implement คัมภีร์ "S20 SMC Liquidity Sniper" ฉบับเต็ม)
      — ใช้ชื่อ S112 เพราะ namespace S20 ชนกับตระกูล S20.x เดิมใน repo

Flow ตามคัมภีร์ (ฝั่ง BUY — SELL กลับด้าน):
  1. HTF Liquidity Sweep — ราคา M1 กวาดใต้ level สำคัญ: Asia Session Low /
     Previous M15 Candle Low / M15 Swing Low ล่าสุด แล้ว "ปฏิเสธ" (close กลับเหนือ level)
  2. LTF CHoCH — M1 close ทะลุ swing high ของโครงสร้างขาลงคลื่นสุดท้าย
     (ยืนยันแท่งแรกที่ปิดเหนือ — แท่งก่อนหน้ายังปิดใต้)
  3. FVG / OB ใน Discount — หา bull FVG (หรือแท่งแดงสุดท้าย = OB) ภายใน
     displacement leg โดยจุด entry ต้องอยู่ครึ่งล่าง (discount) ของ leg
  4. Sniper Entry — Buy Limit ที่ Fibo 50% ของ FVG (fallback: ขอบบน OB)
  5. SL ใต้ low ของแท่ง sweep − buffer 100-150pt / TP = RR 1.5 (หรือ swing แรก)
  6. Breakeven ที่ +1R (ฝั่ง sim จัดการ) / ยกเลิก pending ถ้าไม่ fill ใน 5 แท่ง M1
  7. เทรดเฉพาะ London/NY (ชั่วโมง 14-22 ในเฟรมเวลา backtester ≈ 13:00-21:00 ไทย)

กฎเหล็ก Reality Check: ใช้แท่ง M1 ที่ปิดแล้วเท่านั้น, แท่ง M15 resample ตัดใบที่ยังไม่ครบ,
limit fill ต้องทะลุ spread, SL-first (ฝั่ง sim)
"""

DEFAULT_CFG = {
    "TRADE_HOURS": (14, 15, 16, 17),  # sweep: London open เท่านั้นที่มี edge (NY 20-22 = PF 0.48 ห้ามเทรด)
    "ASIA_HOURS": (7, 8, 9, 10, 11, 12, 13),
    "SWEEP_WINDOW": 30,        # sweep ต้องเกิดภายใน N แท่ง M1 ล่าสุด
    "REJECT_REQUIRED": True,   # แท่ง sweep ต้อง close กลับเหนือ/ใต้ level (wick rejection)
    "M1_PIVOT": 2,             # pivot สำหรับ swing M1 (CHoCH)
    "M15_PIVOT": 2,            # pivot สำหรับ M15 swing level
    "SL_BUF_PTS": 1.2,         # buffer หลัง sweep extreme (USD; 1.2 = 120 points)
    "SL_BUF_PTS_MAX": 1.5,
    "TP_MODE": "rr",           # "rr" | "swing" (swing แรกของโครงสร้าง M1)
    "TP_RR": 2.0,  # sweep: 2.0 > 1.5 > 1.0 ชัด (sniper SL แคบ ต้องปล่อยวิ่ง)
    "ENTRY_PREF": "fvg",       # "fvg" (Fibo50 ของ FVG) แล้ว fallback OB เสมอ
    "MIN_LEG_PTS": 2.0,        # displacement leg ขั้นต่ำ (USD) กัน setup จิ๋ว
    "ML_FILTER_ENABLED": False,
    "ML_SCORE_THRESHOLD": 0.55,
}


def _resample(rates, tf_secs=900):
    """M1 -> M15 (ตัดแท่งที่ยังไม่ครบช่วงทิ้ง — no look-ahead)"""
    out = []
    cur_key, cur = None, None
    for r in rates:
        key = int(r["time"]) // tf_secs
        if key != cur_key:
            if cur is not None:
                out.append(cur)
            cur_key = key
            cur = {"time": key * tf_secs, "open": float(r["open"]),
                   "high": float(r["high"]), "low": float(r["low"]),
                   "close": float(r["close"])}
        else:
            cur["high"] = max(cur["high"], float(r["high"]))
            cur["low"] = min(cur["low"], float(r["low"]))
            cur["close"] = float(r["close"])
    return out  # ไม่รวมใบสุดท้ายที่ยังไม่ปิด


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


def detect_s112(rates, tf="M1", dt_bkk=None, cfg=None, **kwargs):
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    if len(rates) < 700 or dt_bkk is None:
        return {"signal": "WAIT", "reason": "Not enough data / no time"}

    if dt_bkk.hour not in c["TRADE_HOURS"]:
        return {"signal": "WAIT", "reason": f"Outside London/NY window (hour {dt_bkk.hour})"}

    from datetime import datetime as _dt

    m1 = [{"time": int(r["time"]), "open": float(r["open"]), "high": float(r["high"]),
           "low": float(r["low"]), "close": float(r["close"])} for r in rates]
    n = len(m1)
    m15 = _resample(rates)
    if len(m15) < 12:
        return {"signal": "WAIT", "reason": "Not enough M15 context"}

    # ---------- HTF reference levels ----------
    cur_date = dt_bkk.date()
    asia_lo, asia_hi = None, None
    for b in m1:
        d = _dt.fromtimestamp(b["time"])
        if d.date() == cur_date and d.hour in c["ASIA_HOURS"]:
            asia_lo = b["low"] if asia_lo is None else min(asia_lo, b["low"])
            asia_hi = b["high"] if asia_hi is None else max(asia_hi, b["high"])
    prev_m15 = m15[-2]  # แท่ง M15 ที่ปิดแล้วก่อนหน้าล่าสุด
    h15, l15 = _pivots(m15, int(c["M15_PIVOT"]), int(c["M15_PIVOT"]), 60)
    swing_lo_15 = l15[-1][1] if l15 else None
    swing_hi_15 = h15[-1][1] if h15 else None

    buy_refs = [x for x in (asia_lo, prev_m15["low"], swing_lo_15) if x is not None]
    sell_refs = [x for x in (asia_hi, prev_m15["high"], swing_hi_15) if x is not None]

    win = int(c["SWEEP_WINDOW"])
    seg = m1[-win:]
    last = m1[-1]
    prev = m1[-2]

    def _ml_ok(direction, entry):
        if not c["ML_FILTER_ENABLED"]:
            return True, 1.0
        import ml_scoring
        prob = ml_scoring.score_signal('XAUUSD.iux', tf, direction, entry,
                                       dt_bkk, historical_rates=rates)
        return prob >= float(c["ML_SCORE_THRESHOLD"]), prob

    def _result(direction, entry, sl, tp, tag, why):
        return {
            "signal": direction,
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "order_type": "limit",
            "pattern": f"S112 Sniper[{tag}] {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
            "reason": why,
            "candles": [last],
            "be_rr": 1.0,          # breakeven ที่ +1R (ฝั่ง sim/trailing ใช้)
            "cancel_bars": 5,      # ยกเลิก pending ถ้าไม่ fill ใน 5 แท่ง M1
        }

    # =============== BUY ===============
    # 1) sweep bar: low ต่ำกว่า ref ใดๆ + close กลับเหนือ ref
    sweep_i, sweep_low, sweep_ref = None, None, None
    for k in range(len(seg) - 1, -1, -1):
        b = seg[k]
        for ref in buy_refs:
            if b["low"] < ref and (not c["REJECT_REQUIRED"] or b["close"] > ref):
                sweep_i = n - win + k
                sweep_low, sweep_ref = b["low"], ref
                break
        if sweep_i is not None:
            break
    if sweep_i is not None and sweep_i < n - 1:
        # 2) CHoCH: close[-1] ทะลุ swing high (LH) ล่าสุดที่เกิดก่อนหน้า
        h1, _l1 = _pivots(m1[:n - 1], int(c["M1_PIVOT"]), int(c["M1_PIVOT"]), 120)
        lh = None
        for idx, price in reversed(h1):
            if idx < sweep_i:
                lh = price
                break
        if lh is not None and last["close"] > lh >= prev["close"]:
            leg_lo, leg_hi = sweep_low, last["close"]
            leg = leg_hi - leg_lo
            if leg >= float(c["MIN_LEG_PTS"]):
                mid_leg = (leg_lo + leg_hi) / 2.0
                # 3) FVG (bull) ใน leg — เอาตัวที่ mid อยู่ discount
                entry, tag = None, None
                for i in range(n - 2, max(sweep_i, 1), -1):
                    a, ccc = m1[i - 1], m1[i + 1]
                    if ccc["low"] > a["high"]:
                        fvg_mid = (ccc["low"] + a["high"]) / 2.0
                        if fvg_mid <= mid_leg:
                            entry, tag = fvg_mid, "FVG50"
                            break
                if entry is None:
                    # fallback: OB = แท่งแดงสุดท้ายก่อนขาขึ้น (หลัง sweep)
                    for i in range(n - 2, sweep_i - 1, -1):
                        b = m1[i]
                        if b["close"] < b["open"] and b["high"] <= mid_leg:
                            entry, tag = b["high"], "OB"
                            break
                if entry is not None and entry < last["close"]:
                    buf = min(float(c["SL_BUF_PTS_MAX"]), max(float(c["SL_BUF_PTS"]), 1.0))
                    sl = sweep_low - buf
                    risk = entry - sl
                    if risk > 0:
                        if c["TP_MODE"] == "swing" and lh is not None:
                            tp = max(lh, entry + risk)  # swing แรก (อย่างน้อย 1R)
                        else:
                            tp = entry + risk * float(c["TP_RR"])
                        ok, probv = _ml_ok("BUY", entry)
                        if not ok:
                            return {"signal": "WAIT", "reason": f"blocked by ML ({probv:.2f})"}
                        return _result("BUY", entry, sl, tp, tag,
                                       (f"Sweep {sweep_ref:.2f} (low {sweep_low:.2f}) + "
                                        f"M1 CHoCH>{lh:.2f}, entry {tag}"))

    # =============== SELL ===============
    sweep_i, sweep_high, sweep_ref = None, None, None
    for k in range(len(seg) - 1, -1, -1):
        b = seg[k]
        for ref in sell_refs:
            if b["high"] > ref and (not c["REJECT_REQUIRED"] or b["close"] < ref):
                sweep_i = n - win + k
                sweep_high, sweep_ref = b["high"], ref
                break
        if sweep_i is not None:
            break
    if sweep_i is not None and sweep_i < n - 1:
        _h1, l1 = _pivots(m1[:n - 1], int(c["M1_PIVOT"]), int(c["M1_PIVOT"]), 120)
        hl = None
        for idx, price in reversed(l1):
            if idx < sweep_i:
                hl = price
                break
        if hl is not None and last["close"] < hl <= prev["close"]:
            leg_hi, leg_lo = sweep_high, last["close"]
            leg = leg_hi - leg_lo
            if leg >= float(c["MIN_LEG_PTS"]):
                mid_leg = (leg_lo + leg_hi) / 2.0
                entry, tag = None, None
                for i in range(n - 2, max(sweep_i, 1), -1):
                    a, ccc = m1[i - 1], m1[i + 1]
                    if ccc["high"] < a["low"]:
                        fvg_mid = (ccc["high"] + a["low"]) / 2.0
                        if fvg_mid >= mid_leg:
                            entry, tag = fvg_mid, "FVG50"
                            break
                if entry is None:
                    for i in range(n - 2, sweep_i - 1, -1):
                        b = m1[i]
                        if b["close"] > b["open"] and b["low"] >= mid_leg:
                            entry, tag = b["low"], "OB"
                            break
                if entry is not None and entry > last["close"]:
                    buf = min(float(c["SL_BUF_PTS_MAX"]), max(float(c["SL_BUF_PTS"]), 1.0))
                    sl = sweep_high + buf
                    risk = sl - entry
                    if risk > 0:
                        if c["TP_MODE"] == "swing" and hl is not None:
                            tp = min(hl, entry - risk)
                        else:
                            tp = entry - risk * float(c["TP_RR"])
                        ok, probv = _ml_ok("SELL", entry)
                        if not ok:
                            return {"signal": "WAIT", "reason": f"blocked by ML ({probv:.2f})"}
                        return _result("SELL", entry, sl, tp, tag,
                                       (f"Sweep {sweep_ref:.2f} (high {sweep_high:.2f}) + "
                                        f"M1 CHoCH<{hl:.2f}, entry {tag}"))

    return {"signal": "WAIT", "reason": "No sweep + CHoCH + FVG/OB setup"}
