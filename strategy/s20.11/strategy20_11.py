"""
strategy20_11.py — S20.11 Candle Strength (Institutional Price Action)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sub-patterns (ท่าย่อยตามฉบับ การอ่านเเรงเเท่งเทียน.pdf):
  S20.11.CandleStrength_Retest: ดักเข้า 50% ของ Sponsor Candle (เนื้อเทียน) เมื่อราคาย้อนกลับมา + ยืนยัน Rejection
"""

from datetime import time
import config
from mt5_utils import calc_atr

def strategy_20_11(rates, tf_name="M5", config=config) -> dict:
    res = {"signal": "WAIT", "reason": "", "pattern": "S20.11", "sid": 20.11}

    if not getattr(config, "S20_11_ENABLED", False):
        res["reason"] = "S20.11 is disabled"
        return res

    if getattr(config, "S20_11_TF_ENABLED", {}).get(tf_name) is False:
        res["reason"] = f"S20.11 is disabled for {tf_name}"
        return res

    if rates is None or len(rates) < 20:
        res["reason"] = "S20.11 - ข้อมูลไม่พอ"
        return res

    atr = calc_atr(rates[:-1], 14) or 1.0
    c_curr = rates[-1]
    c_prev1 = rates[-2]
    
    recent_rates = rates[-20:-2]
    if len(recent_rates) == 0:
        return res
        
    signal = None
    sub_pattern = None
    entry_price = 0.0
    sl = 0.0
    
    # 1. ค้นหา Sponsor Candle ย้อนหลังไปไม่เกิน 15 แท่ง
    # Sponsor Candle ฝั่ง BUY: แท่งเขียวปิดคลุมไส้ (High) ของแท่งก่อนหน้า
    # Sponsor Candle ฝั่ง SELL: แท่งแดงปิดคลุมไส้ (Low) ของแท่งก่อนหน้า
    for i in range(len(rates) - 3, max(0, len(rates) - 15), -1):
        c_s = rates[i]
        c_s_prev = rates[i-1]
        
        body_size_s = abs(c_s['close'] - c_s['open'])
        mid_body = (c_s['open'] + c_s['close']) / 2.0
        
        is_bullish_disp = (c_s['close'] > c_s['open']) and (c_s['close'] > c_s_prev['high']) and body_size_s > (atr * 0.4)
        is_bearish_disp = (c_s['close'] < c_s['open']) and (c_s['close'] < c_s_prev['low']) and body_size_s > (atr * 0.4)
        
        if is_bullish_disp:
            # 2. เช็คว่าโครงสร้างยังไม่ถูกทำลาย (ยังไม่หลุด Low ของ Sponsor)
            lowest_since = min(r['low'] for r in rates[i+1:-1])
            if lowest_since < c_s['low']:
                continue
                
            # 3. เช็คการย้อนมารับของที่ 50%
            touched = False
            for k in range(i+1, len(rates) - 1):
                if rates[k]['low'] <= mid_body:
                    touched = True
                    break
                    
            if touched and c_prev1['low'] <= mid_body and c_prev1['close'] > mid_body:
                # 4. Confirmation: ปิดเขียว (Reaction) หรือ Doji (หมดแรงขาย)
                body_prev1 = abs(c_prev1['close'] - c_prev1['open'])
                is_green = c_prev1['close'] > c_prev1['open']
                is_doji = body_prev1 < (atr * 0.25)
                # ปิดไม่คลุมไส้ล่างแท่งก่อนหน้า (ยืนยัน Exhaustion)
                c_prev2 = rates[-3]
                not_engulf_down = c_prev1['close'] >= c_prev2['low']
                
                if (is_green or is_doji) and not_engulf_down:
                    signal = "BUY"
                    sub_pattern = "S20.11.CandleStrength_Retest"
                    entry_price = c_prev1['close']
                    sl = c_s['low'] - (atr * 0.3)
                    break
                    
        elif is_bearish_disp:
            # 2. เช็คว่าโครงสร้างยังไม่ถูกทำลาย (ยังไม่ทะลุ High ของ Sponsor)
            highest_since = max(r['high'] for r in rates[i+1:-1])
            if highest_since > c_s['high']:
                continue
                
            # 3. เช็คการย้อนมารับของที่ 50%
            touched = False
            for k in range(i+1, len(rates) - 1):
                if rates[k]['high'] >= mid_body:
                    touched = True
                    break
                    
            if touched and c_prev1['high'] >= mid_body and c_prev1['close'] < mid_body:
                # 4. Confirmation: ปิดแดง (Reaction) หรือ Doji (หมดแรงซื้อ)
                body_prev1 = abs(c_prev1['close'] - c_prev1['open'])
                is_red = c_prev1['close'] < c_prev1['open']
                is_doji = body_prev1 < (atr * 0.25)
                # ปิดไม่คลุมไส้บนแท่งก่อนหน้า (ยืนยัน Exhaustion)
                c_prev2 = rates[-3]
                not_engulf_up = c_prev1['close'] <= c_prev2['high']
                
                if (is_red or is_doji) and not_engulf_up:
                    signal = "SELL"
                    sub_pattern = "S20.11.CandleStrength_Retest"
                    entry_price = c_prev1['close']
                    sl = c_s['high'] + (atr * 0.3)
                    break
                    
    if not signal:
        return res

    # 5. กำหนด TP (Target)
    if signal == "BUY":
        # เป้าหมายคือ High ของคลื่นนี้ หรืออย่างน้อย RR 1:1.5
        recent_high = max(r['high'] for r in rates[-15:-1])
        tp = max(recent_high, entry_price + (entry_price - sl) * 1.5)
    else:
        # เป้าหมายคือ Low ของคลื่นนี้ หรืออย่างน้อย RR 1:1.5
        recent_low = min(r['low'] for r in rates[-15:-1])
        tp = min(recent_low, entry_price - (sl - entry_price) * 1.5)

    res["signal"] = signal
    res["entry"] = round(entry_price, 2)
    res["sl"] = round(sl, 2)
    res["tp"] = round(tp, 2)
    res["reason"] = f"S20.11 - {sub_pattern}"
    res["pattern"] = sub_pattern
    return res
