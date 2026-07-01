"""
strategy20_10.py — S20.10 Allin4s_2 (Wick Purge & Reversal Trap)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sub-patterns (ท่าย่อยตามฉบับ Sarawut.pdf):
  S20.10.DM_Trap: ดัก Sell ที่ปลายไส้ตำหนิฝั่งบน (Rejection at premium) - รูปแบบหลอกล่าสภาพคล่อง Demand
  S20.10.SP_Trap: ดัก Buy ที่ปลายไส้ตำหนิฝั่งล่าง (Rejection at discount) - รูปแบบหลอกล่าสภาพคล่อง Supply
  S20.10.Fakeout_SP: วิ่งแตะ SP แล้วย้อนหาไส้ล่าง (Sniper Entry) - รูปแบบ SP ล่อสังหาร
"""

from datetime import time
import config
from mt5_utils import calc_atr

def _apply_psychological_number(price: float, is_buy: bool, is_tp: bool) -> float:
    """VIP Rule: Adjusts the price to end in 7 or 8. Avoids 0 and 5."""
    if not getattr(config, "S20_10_USE_PSYCHOLOGICAL_NUMBERS", True):
        return price
        
    int_price = int(price)
    last_digit = int_price % 10
    
    offset = 0
    if last_digit in (0, 1, 2):
        offset = - (last_digit + 2)  
    elif last_digit in (3, 4, 5, 6):
        offset = (8 - last_digit)    
    elif last_digit == 9:
        offset = -1                  
        
    if last_digit == 7:
        offset = 0
        
    return float(int_price + offset) + (price - int_price)

def strategy_20_10(rates, tf_name="M5", config=config) -> dict:
    res = {"signal": "WAIT", "reason": "", "pattern": "S20.10", "sid": 20.10}

    if not getattr(config, "S20_10_ENABLED", False):
        res["reason"] = "S20.10 is disabled"
        return res

    if rates is None or len(rates) < 20:
        res["reason"] = "S20.10 - ข้อมูลไม่พอ"
        return res

    atr = calc_atr(rates[:-1], 14) or 1.0
    c_curr = rates[-1]
    c_prev1 = rates[-2]
    
    recent_rates = rates[-20:-2]
    if len(recent_rates) == 0:
        return {"signal": None, "reason": "No rates"}
        
    recent_high = max(r['high'] for r in recent_rates)
    recent_low = min(r['low'] for r in recent_rates)
    
    signal = None
    sub_pattern = None
    ref_bar = c_prev1

    wick_top_prev = c_prev1['high'] - max(c_prev1['open'], c_prev1['close'])
    wick_bot_prev = min(c_prev1['open'], c_prev1['close']) - c_prev1['low']
    body_prev = abs(c_prev1['open'] - c_prev1['close'])

    # S20.10.DM_Trap (SELL Limit) - Page 12: แทงทะลุ DM ด้วยไส้ (Sweep) แล้วปิดกลับขึ้นมา
    if c_prev1['high'] > recent_high and c_prev1['close'] <= recent_high:
        if wick_top_prev > body_prev and wick_top_prev > (atr * 0.5): 
            signal, sub_pattern = "SELL", "S20.10.DM_Trap"
            
    # S20.10.SP_Trap (BUY Limit) - Page 13: แทงทะลุ SP ด้วยไส้ (Sweep) แล้วปิดกลับลงมา
    if not signal and c_prev1['low'] < recent_low and c_prev1['close'] >= recent_low:
        if wick_bot_prev > body_prev and wick_bot_prev > (atr * 0.5):
            signal, sub_pattern = "BUY", "S20.10.SP_Trap"

    # S20.10.Fakeout_SP (BUY Limit) - Page 40: SP ล่อสังหาร ย้อนกลับมาหาไส้ล่าสุด
    if not signal and c_prev1['high'] >= recent_high:
        if c_curr['open'] < c_prev1['close']: # เริ่มย้อน
            if wick_bot_prev > (atr * 0.3): # มีไส้ล่างเป็นตำหนิเดิม
                signal, sub_pattern = "BUY", "S20.10.Fakeout_SP"

    if not signal:
        return res

    entry_buffer = atr * 0.1
    if signal == "BUY":
        if sub_pattern == "S20.10.Fakeout_SP":
            entry = ref_bar['low'] + (atr * 0.05) # Sniper ที่ปลายไส้ล่าสุด
        else:
            entry = ref_bar['low'] + entry_buffer
        sl = entry - (atr * 1.5)
        tp = entry + (atr * 2.5)
    else:
        entry = ref_bar['high'] - entry_buffer
        sl = entry + (atr * 1.5)
        tp = entry - (atr * 2.5)

    if getattr(config, "S20_10_USE_PSYCHOLOGICAL_NUMBERS", True):
        entry = _apply_psychological_number(entry, is_buy=(signal=="BUY"), is_tp=False)
        tp = _apply_psychological_number(tp, is_buy=(signal=="BUY"), is_tp=True)

    # Protect RR
    if signal == "BUY":
        tp = max(tp, entry + atr)
        sl = min(sl, entry - (atr*0.2))
    else:
        tp = min(tp, entry - atr)
        sl = max(sl, entry + (atr*0.2))

    res["signal"] = signal
    res["entry"] = round(entry, 2)
    res["sl"] = round(sl, 2)
    res["tp"] = round(tp, 2)
    res["reason"] = f"S20.10 - {sub_pattern}"
    res["pattern"] = sub_pattern
    return res
