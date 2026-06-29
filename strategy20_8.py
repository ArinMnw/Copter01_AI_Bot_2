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
    
    buffer_pts = getattr(config, "S20_8_ENTRY_BUFFER_POINTS", 300.0) 
    sl_pts = getattr(config, "S20_8_SL_POINTS", 100.0)
    tp_pts = getattr(config, "S20_8_TP_POINTS", 700.0)
    pt_mult = getattr(config, "S20_8_POINTS_MULTIPLIER", 0.01)
    
    # เงื่อนไข Rejection (Pa BUY หลอก / Pa SELL หลอก หรือแท่งตัน)
    valid_buy_rejection = (is_red and lower_wick_pct <= 0.15) or (is_green and body_pct >= 0.70 and lower_wick_pct <= 0.15)
    valid_sell_rejection = (is_green and upper_wick_pct <= 0.15) or (is_red and body_pct >= 0.70 and upper_wick_pct <= 0.15)
    
    if valid_buy_rejection:
        # หาโครงสร้าง Small 2L: ก่อนหน้ามีแท่งเขียวดันขึ้น 2-3 แท่ง แล้วแท่งปัจจุบัน(แดง) กดลงมาไม่หลุด Low ของชุดเขียว
        green_push = 0
        prev_low = float('inf')
        for i in range(2, 6):
            b = rates[-i]
            if float(b["close"]) > float(b["open"]):
                green_push += 1
                prev_low = min(prev_low, float(b["low"]))
            else:
                break
                
        if green_push >= 1 and _low >= (prev_low - 0.5): # ไม่หลุด Low เดิม
            signal = "BUY"
            entry = _low - (buffer_pts * pt_mult) # เผื่อระยะกินไส้
            sl = entry - (sl_pts * pt_mult)
            tp = entry + (tp_pts * pt_mult)
            
    elif valid_sell_rejection:
        # หาโครงสร้าง Small 2H: ก่อนหน้ามีแท่งแดงกดลง 2-3 แท่ง แล้วแท่งปัจจุบัน(เขียว) ดันขึ้นไม่ทะลุ High ของชุดแดง
        red_push = 0
        prev_high = float('-inf')
        for i in range(2, 6):
            b = rates[-i]
            if float(b["close"]) < float(b["open"]):
                red_push += 1
                prev_high = max(prev_high, float(b["high"]))
            else:
                break
                
        if red_push >= 1 and _high <= (prev_high + 0.5): # ไม่ทะลุ High เดิม
            signal = "SELL"
            entry = _high + (buffer_pts * pt_mult)
            sl = entry + (sl_pts * pt_mult)
            tp = entry - (tp_pts * pt_mult)

    if signal != "WAIT":
        return {
            "signal": signal,
            "pattern": "S20.8 Small2L2H",
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "reason": f"S20.8 {signal} at Local {'Low (2L)' if signal == 'BUY' else 'High (2H)'}",
            "sid": 20.8
        }
        
    return {"signal": "WAIT", "reason": "S20.8 No valid small 2L/2H structure", "pattern": "S20.8", "sid": 20.8}
