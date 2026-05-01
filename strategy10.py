"""
ท่าที่ 10 — CRT TBS (Candle Range Theory + Three Bar Sweep)

แนวคิด: liquidity sweep + close กลับเข้าในกรอบ = false break = สัญญาณกลับ
ใช้ 3 แท่งล่าสุด (rates[-3]=parent, rates[-2]=sweep, rates[-1]=confirm)

เงื่อนไข:
  BUY  — sweep[low]  < parent[low]  AND confirm[close] > parent[low]   (sweep ต่ำ + close กลับ)
  SELL — sweep[high] > parent[high] AND confirm[close] < parent[high]  (sweep สูง + close กลับ)

Order:
  Entry — Market ตอน confirm candle close (= ตอน scanner สแกนรอบนี้)
  SL    — ปลาย wick ของ sweep + buffer (CRT_SL_BUFFER_POINTS)
  TP    — ขอบตรงข้ามของ parent range
"""

from config import crt_min_range_price, crt_sl_buffer_price


def strategy_10(rates):
    if len(rates) < 4:
        return {"signal": "WAIT", "reason": "ข้อมูลไม่พอ (ต้องการอย่างน้อย 4 แท่ง)"}

    parent  = rates[-3]
    sweep   = rates[-2]
    confirm = rates[-1]

    p_open  = float(parent["open"])
    p_high  = float(parent["high"])
    p_low   = float(parent["low"])
    p_close = float(parent["close"])

    s_open  = float(sweep["open"])
    s_high  = float(sweep["high"])
    s_low   = float(sweep["low"])
    s_close = float(sweep["close"])

    c_open  = float(confirm["open"])
    c_high  = float(confirm["high"])
    c_low   = float(confirm["low"])
    c_close = float(confirm["close"])

    p_range = p_high - p_low
    min_range = crt_min_range_price()
    if p_range < min_range:
        return {
            "signal": "WAIT",
            "reason": f"Parent range เล็กไป ({p_range:.2f} < {min_range:.2f})",
        }

    buffer = crt_sl_buffer_price()
    candles = [
        {"open": p_open, "high": p_high, "low": p_low, "close": p_close},
        {"open": s_open, "high": s_high, "low": s_low, "close": s_close},
        {"open": c_open, "high": c_high, "low": c_low, "close": c_close},
    ]

    confirm_bull = c_close > c_open
    confirm_bear = c_close < c_open

    # ── CRT BUY: sweep low + close กลับเข้าใน range + confirm เขียว ──
    if s_low < p_low and c_close > p_low and confirm_bull:
        entry = round(c_close, 2)
        sl    = round(s_low - buffer, 2)
        tp    = round(p_high, 2)
        if not (sl < entry < tp):
            return {"signal": "WAIT", "reason": "BUY SL/TP ไม่ valid (ลำดับราคาผิด)"}
        risk = entry - sl
        rr = round((tp - entry) / risk, 2) if risk > 0 else 0
        return {
            "signal": "BUY",
            "pattern": "ท่าที่ 10 CRT TBS 🟢 BUY — Sweep Low",
            "entry": entry, "sl": sl, "tp": tp,
            "order_mode": "market",
            "reason": (
                f"Parent[H:{p_high:.2f} L:{p_low:.2f}] "
                f"Sweep[L:{s_low:.2f}<{p_low:.2f}] "
                f"Confirm🟢[O:{c_open:.2f} C:{c_close:.2f}>{p_low:.2f}]\n"
                f"Entry:{entry} SL:{sl} TP:{tp} RR1:{rr}"
            ),
            "candles": candles,
        }

    # ── CRT SELL: sweep high + close กลับเข้าใน range + confirm แดง ──
    if s_high > p_high and c_close < p_high and confirm_bear:
        entry = round(c_close, 2)
        sl    = round(s_high + buffer, 2)
        tp    = round(p_low, 2)
        if not (tp < entry < sl):
            return {"signal": "WAIT", "reason": "SELL SL/TP ไม่ valid (ลำดับราคาผิด)"}
        risk = sl - entry
        rr = round((entry - tp) / risk, 2) if risk > 0 else 0
        return {
            "signal": "SELL",
            "pattern": "ท่าที่ 10 CRT TBS 🔴 SELL — Sweep High",
            "entry": entry, "sl": sl, "tp": tp,
            "order_mode": "market",
            "reason": (
                f"Parent[H:{p_high:.2f} L:{p_low:.2f}] "
                f"Sweep[H:{s_high:.2f}>{p_high:.2f}] "
                f"Confirm🔴[O:{c_open:.2f} C:{c_close:.2f}<{p_high:.2f}]\n"
                f"Entry:{entry} SL:{sl} TP:{tp} RR1:{rr}"
            ),
            "candles": candles,
        }

    return {"signal": "WAIT", "reason": "ไม่พบ CRT TBS Setup"}
