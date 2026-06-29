"""
strategy20_7.py — S20.7 All in 4s 1 (Defect & Wick Fill Divergence)
"""
import config
from mt5_utils import calc_atr

def strategy_20_7(rates, tf="M5", dt_bkk=None) -> dict:
    res = {"signal": "WAIT", "reason": "", "pattern": "S20.7_Allin4s_1", "sid": 20.7}
    
    # Check if strategy is enabled in config
    is_active = getattr(config, "active_strategies", {}).get(20.7, False)
    is_enabled = getattr(config, "S20_7_ENABLED", False)
    if not (is_active or is_enabled):
        res["reason"] = "S20.7 - ปิดใช้งาน"
        return res

    if rates is None or len(rates) < 60:
        res["reason"] = "S20.7 - ข้อมูลไม่พอ"
        return res

    atr = calc_atr(rates[:-1], 14) or 1.0
    c_curr = rates[-1]
    c_prev1 = rates[-2]
    
    def is_green(c): return c['close'] > c['open']
    def is_red(c): return c['close'] < c['open']
    
    # 1. การตรวจจับการกวาดสภาพคล่อง (Liquidity Sweep)
    # หาราคาสูงสุด/ต่ำสุดในรอบ 60 แท่ง (ไม่รวมแท่งปัจจุบัน)
    recent_rates = rates[-61:-1]
    recent_high = max(r['high'] for r in recent_rates)
    recent_low  = min(r['low']  for r in recent_rates)
    
    is_sweep_low = c_curr['low'] <= recent_low or c_prev1['low'] <= recent_low
    is_sweep_high = c_curr['high'] >= recent_high or c_prev1['high'] >= recent_high
    
    signal = None
    ref_bar = None
    reason_details = []
    
    # 2. การหาแท่งตำหนิ (Defect Candle) และ Wick Rejection
    # เงื่อนไข Wick Length >= 50% ของ Candle Range
    curr_range = c_curr['high'] - c_curr['low']
    if curr_range <= 0.00001:
        return res
        
    bottom_wick = min(c_curr['open'], c_curr['close']) - c_curr['low']
    top_wick = c_curr['high'] - max(c_curr['open'], c_curr['close'])
    
    # BUY: ราคาลงไปกวาด Liquidity ด้านล่าง -> เกิดแรงซื้อกลับ (Wick Rejection)
    # แท่งก่อนหน้าแดง -> แท่งปัจจุบันเขียว กลืนเนื้อแดง แต่ "ปิดไม่พ้นไส้บน" ของแดง
    if is_sweep_low and is_red(c_prev1) and is_green(c_curr):
        if c_curr['close'] > c_prev1['open'] and c_curr['close'] < c_prev1['high']:
            if (bottom_wick / curr_range) >= 0.50:
                signal = "BUY"
                ref_bar = c_curr
                reason_details = ["Sweep Low", "Engulf Body", "Wick Reject >= 50%"]
                
    # SELL: ราคาขึ้นไปกวาด Liquidity ด้านบน -> เกิดแรงขายกลับ (Wick Rejection)
    # แท่งก่อนหน้าเขียว -> แท่งปัจจุบันแดง กลืนเนื้อเขียว แต่ "ปิดไม่พ้นไส้ล่าง" ของเขียว
    if is_sweep_high and is_green(c_prev1) and is_red(c_curr):
        if c_curr['close'] < c_prev1['open'] and c_curr['close'] > c_prev1['low']:
            if (top_wick / curr_range) >= 0.50:
                signal = "SELL"
                ref_bar = c_curr
                reason_details = ["Sweep High", "Engulf Body", "Wick Reject >= 50%"]

    if not signal:
        return res
        
    # 3. การกำหนดจุดเข้าและออก (Wick Fill 50%)
    if signal == "BUY":
        # จุดเข้ารอที่ 50% ของไส้ล่างแท่งตำหนิ
        wick_top = min(ref_bar['open'], ref_bar['close'])
        wick_bottom = ref_bar['low']
        entry = (wick_top + wick_bottom) / 2.0
        
        # Stop Loss ที่ Extreme Wick + ATR Buffer
        sl_dist = atr * 1.0
        sl = wick_bottom - sl_dist
        
        # Take Profit ที่ Fibo 1.618 ของรอบการกลับตัว (ใช้ swing ของ 2 แท่งล่าสุด)
        swing_dist = ref_bar['high'] - ref_bar['low']
        tp = entry + (swing_dist * 1.618)
        
    else: # SELL
        # จุดเข้ารอที่ 50% ของไส้บนแท่งตำหนิ
        wick_bottom = max(ref_bar['open'], ref_bar['close'])
        wick_top = ref_bar['high']
        entry = (wick_top + wick_bottom) / 2.0
        
        # Stop Loss ที่ Extreme Wick + ATR Buffer
        sl_dist = atr * 1.0
        sl = wick_top + sl_dist
        
        # Take Profit ที่ Fibo 1.618 ของรอบการกลับตัว
        swing_dist = ref_bar['high'] - ref_bar['low']
        tp = entry - (swing_dist * 1.618)
    
    # 4. Target Points Limit Safety (ป้องกัน TP สั้นหรือยาวเกิน)
    # 1.0 USD = 100 points
    min_tp_dist = 5.0 # 500 points
    if signal == "BUY" and (tp - entry) < min_tp_dist:
        tp = entry + min_tp_dist
    elif signal == "SELL" and (entry - tp) < min_tp_dist:
        tp = entry - min_tp_dist
        
    reason_str = "S20.7 - " + " + ".join(reason_details)
    
    res.update({
        "signal": signal,
        "entry": round(entry, 2),
        "sl": round(sl, 2),
        "tp": round(tp, 2),
        "price": round(c_curr['close'], 2),
        "reason": reason_str
    })
    
    return res

