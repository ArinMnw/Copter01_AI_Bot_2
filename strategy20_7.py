import config
from mt5_utils import calc_atr

def strategy_20_7(rates, tf="M5", dt_bkk=None) -> dict:
    """
    S20.7 - ท่าไม้ตายอออิน4วิ 1 (Defect Candle & Wick Fill Divergence)
    ตรรกะ: ดักรอแท่งตำหนิ (ปิดไม่คลุมไส้) ที่ High/Low และตั้ง Pending ดักรอที่ปลายไส้ของมันเอง
    """
    res = {"signal": "WAIT", "reason": "", "pattern": "S20.7", "sid": 20.7}
    
    if not getattr(config, "S20_7_ENABLED", False):
        return res
        
    if rates is None or len(rates) < 20:
        return res

    atr = calc_atr(rates[:-1], 14) or 1.0
    c_curr = rates[-1]    # แท่งตำหนิ (Defect)
    c_prev1 = rates[-2]   # แท่งอ้างอิงเดิม
    
    def is_green(c): return c['close'] > c['open']
    def is_red(c): return c['close'] < c['open']
    
    # หาสภาวะ Swing High / Low ในรอบ 20 แท่ง
    recent_rates = rates[-20:]
    recent_high = max(r['high'] for r in recent_rates)
    recent_low = min(r['low'] for r in recent_rates)
    
    is_swing_high = (c_curr['high'] >= recent_high or c_prev1['high'] >= recent_high)
    is_swing_low = (c_curr['low'] <= recent_low or c_prev1['low'] <= recent_low)
    
    signal = None
    entry = sl = tp = 0.0

    # ---------------------------------------------------------
    # BUY SETUP: แท่งก่อนหน้าแดง -> แท่งปัจจุบันเขียว (กลืนเนื้อ แต่ปิดต่ำกว่าไส้บนแดง)
    # ---------------------------------------------------------
    if is_swing_low and is_red(c_prev1) and is_green(c_curr):
        if c_curr['close'] > c_prev1['open'] and c_curr['close'] < c_prev1['high']:
            signal = "BUY"

    # ---------------------------------------------------------
    # SELL SETUP: แท่งก่อนหน้าเขียว -> แท่งปัจจุบันแดง (กลืนเนื้อ แต่ปิดสูงกว่าไส้ล่างเขียว)
    # ---------------------------------------------------------
    elif is_swing_high and is_green(c_prev1) and is_red(c_curr):
        if c_curr['close'] < c_prev1['open'] and c_curr['close'] > c_prev1['low']:
            signal = "SELL"

    if not signal:
        return res
        
    # ── Calculate Entry, SL, TP (Mimicking old strategy20.py) ──
    tf_max_wick = {"M1": 50.0, "M5": 310.0, "M15": 363.0, "M30": 621.0, "H1": 1200.0, "H4": 2100.0, "H12": 3500.0, "D1": 3390.0}
    base_wick = 310.0
    tf_scale = tf_max_wick.get(tf, base_wick) / base_wick
    
    entry_buffer = getattr(config, "S20_ENTRY_BUFFER", 0.0) * tf_scale * 0.01
    sl_2l2h = atr * 1.5
    
    fibo_run = 2.0 # Defect candle wick fill target
    if getattr(config, "S20_DYNAMIC_FIBO", True):
        anchor_size = abs(c_prev1['high'] - c_prev1['low'])
        if anchor_size > (atr * 1.5):
            fibo_run = min(fibo_run, 3.097)

    # Base points from the swing
    base_low = min(c_prev1['low'], c_curr['low'])
    base_high = max(c_prev1['high'], c_curr['high'])

    if signal == "BUY":
        entry = base_low + entry_buffer
        sl_raw = base_low - sl_2l2h
    else:
        entry = base_high - entry_buffer
        sl_raw = base_high + sl_2l2h
        
    sl = sl_raw
    
    low_pt = base_low
    high_pt = base_high
    
    if signal == "BUY":
        tp_raw = sl_raw + ((high_pt - sl_raw) * fibo_run)
        tp_raw = max(tp_raw, entry + atr)
        sl = min(sl, entry - (atr * 0.2))
    else:
        tp_raw = sl_raw - ((sl_raw - low_pt) * fibo_run)
        tp_raw = min(tp_raw, entry - atr)
        sl = max(sl, entry + (atr * 0.2))

    return {
        "signal": signal,
        "entry": round(entry, 2),
        "sl": round(sl, 2),
        "tp": round(tp_raw, 2),
        "price": round(entry, 2),
        "reason": f"S20.7 - Defect Candle Wick Entry",
        "pattern": "S20.7_Ultimate_1",
        "sid": 20.7
    }
