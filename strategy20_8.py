import config as _config

def strategy_20_8(rates, tf="M1", tf_name=None, config=None) -> dict:
    if config is None:
        config = _config
    
    """
    ท่าไม้ตายอออิน4วิ 2 (Small 2L/2H & Wick Rejection Sniper) S20.8
    เล่น TF เล็ก (M1-M30) จับโครงสร้าง 2L/2H ที่รายใหญ่กวาด Liquidity แบบไม่ทะลุฐานเดิม
    """
    if not getattr(config, "S20_8_ENABLED", False):
        return {"signal": "WAIT", "reason": "S20.8 disabled", "pattern": "S20.8", "sid": 20.8}
        
    if rates is None or len(rates) < 15:
        return {"signal": "WAIT", "reason": "Not enough rates", "pattern": "S20.8", "sid": 20.8}
        
    # เช็กระยะความผันผวนของ TF (ห้ามเข้าถ้าไส้วิ่งแรงเกิน 2000 จุด)
    for r in rates[-15:]:
        if (float(r["high"]) - float(r["low"])) > 20.00: 
            return {"signal": "WAIT", "reason": "High volatility > 2000 pts", "pattern": "S20.8", "sid": 20.8}
    
    current_bar = rates[-1]
    _open = float(current_bar["open"])
    _close = float(current_bar["close"])
    _high = float(current_bar["high"])
    _low = float(current_bar["low"])
    
    range_total = max(abs(_high - _low), 0.0001)
    body = abs(_close - _open)
    body_pct = body / range_total
    
    is_green = _close > _open
    is_red = _close < _open
    
    upper_wick = _high - max(_open, _close)
    lower_wick = min(_open, _close) - _low
    
    upper_wick_pct = upper_wick / range_total
    lower_wick_pct = lower_wick / range_total
    
    signal = "WAIT"
    entry = 0.0
    sl = 0.0
    tp = 0.0
    
    pt_mult = getattr(config, "S20_8_POINTS_MULTIPLIER", 0.01)
    
    # Calculate Dynamic ATR
    tr_list = []
    for i in range(1, min(15, len(rates))):
        c0 = rates[-i]
        c1 = rates[-(i+1)]
        hl = float(c0["high"]) - float(c0["low"])
        hc = abs(float(c0["high"]) - float(c1["close"]))
        lc = abs(float(c0["low"]) - float(c1["close"]))
        tr_list.append(max(hl, hc, lc))
    atr_price = sum(tr_list) / len(tr_list) if tr_list else range_total
    atr_pts = atr_price / pt_mult
    
    # 🔥 Dynamic Risk Management for Consistent 1:1.5 RR Growth
    # ปรับใช้ ATR เพื่อให้ยืดหยุ่นตามสภาวะตลาด
    buffer_pts = max(150.0, atr_pts * 0.5) 
    sl_pts = max(150.0, atr_pts * 1.0)
    tp_pts = sl_pts * 1.5 # RR 1:1.5

    # 🛡️ Institutional Momentum Filter
    # ป้องกันการเข้าสวนเทรนด์ที่สถาบันกำลังทุบ/ดันอย่างรุนแรง (Displacement)
    prev_candle = rates[-2]
    prev_body = abs(float(prev_candle["close"]) - float(prev_candle["open"]))
    if prev_body > (atr_price * 2.0):
        return {"signal": "WAIT", "reason": "Institutional Displacement Block", "pattern": "S20.8", "sid": 20.8}

    # 🔬 เงื่อนไข Rejection & Sweep Confirmation
    # ปรับแก้จากเดิมที่ห้ามทะลุ เป็นอนุญาตให้ทะลุเพื่อกวาด SL (Sweep) ได้ แต่บังคับว่าต้องทิ้งหางกลับมาปิด (Failure to Close)
    valid_buy_rejection = (lower_wick_pct >= 0.25) or (is_green and body_pct >= 0.60 and lower_wick_pct >= 0.15)
    valid_sell_rejection = (upper_wick_pct >= 0.25) or (is_red and body_pct >= 0.60 and upper_wick_pct >= 0.15)
    
    if valid_buy_rejection:
        # หาโครงสร้าง Small 2L: ก่อนหน้ามีแท่งเขียวดันขึ้น 2-3 แท่ง
        green_push = 0
        prev_low = float('inf')
        for i in range(2, 6):
            b = rates[-i]
            if float(b["close"]) > float(b["open"]):
                green_push += 1
                prev_low = min(prev_low, float(b["low"]))
            else:
                break
                
        # Liquidity Sweep Rule: ยอมให้ _low หลุด prev_low ได้เพื่อตวัดกินไส้ แต่ _close ต้องเด้งกลับมาปิดเหนือฐาน หรือห่างไม่เกินนิดเดียว
        if green_push >= 1 and _close >= (prev_low - 0.2): 
            signal = "BUY"
            entry = _low - (buffer_pts * pt_mult) # เผื่อระยะกินไส้
            sl = entry - (sl_pts * pt_mult)
            tp = entry + (tp_pts * pt_mult)
    elif valid_sell_rejection:
        # หาโครงสร้าง Small 2H: ก่อนหน้ามีแท่งแดงกดลง 2-3 แท่ง
        red_push = 0
        prev_high = float('-inf')
        for i in range(2, 6):
            b = rates[-i]
            if float(b["close"]) < float(b["open"]):
                red_push += 1
                prev_high = max(prev_high, float(b["high"]))
            else:
                break
                
        # Liquidity Sweep Rule: ยอมให้ _high ทะลุ prev_high ได้เพื่อกวาด SL แต่ _close ต้องโดนตบกลับมาปิดใต้แนว
        if red_push >= 1 and _close <= (prev_high + 0.2): 
            signal = "SELL"
            entry = _high + (buffer_pts * pt_mult)
            sl = entry + (sl_pts * pt_mult)
            tp = entry - (tp_pts * pt_mult)
    if signal != "WAIT":
        return {
            "signal": signal,
            "pattern": "S20.8 Small2L2H",
            "entry": round(entry, 5),
            "sl": round(sl, 5),
            "tp": round(tp, 5),
            "reason": f"S20.8 {signal} at Local {'Low (2L)' if signal == 'BUY' else 'High (2H)'}",
            "sid": 20.8
        }
        
    reason = locals().get("reason_override", "S20.8 No valid small 2L/2H structure")
    return {"signal": "WAIT", "reason": reason, "pattern": "S20.8", "sid": 20.8}
