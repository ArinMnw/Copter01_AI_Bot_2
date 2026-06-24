import config
from mt5_utils import calc_atr

def strategy_20_9(rates, tf="M5", dt_bkk=None) -> dict:
    """
    S20.9 - Candle Action Reversal (การอ่านเเรงเเท่งเทียน)
    ตรรกะ: หากแท่งเทียนปัจจุบันมีเนื้อเทียนหนาเกิน 35% ของ range และกลืนกินแท่งก่อนหน้า
    ให้รอเข้าที่ 50% ของแท่งปัจจุบันเพื่อ Pullback
    """
    res = {"signal": "WAIT", "reason": "", "pattern": "S20.9", "sid": 20.9}
    
    if rates is None or len(rates) < 4:
        return res
        
    c_curr = rates[-1]
    c_prev1 = rates[-2]
    atr = calc_atr(rates[:-1], 14) or 1.0
    
    def is_green(c): return c['close'] > c['open']
    def is_red(c): return c['close'] < c['open']
    def body_size(c): return abs(c['close'] - c['open'])
    def candle_range(c): return abs(c['high'] - c['low'])
    
    # 0.35 body size criteria
    def has_strong_body(c):
        rng = candle_range(c)
        if rng == 0: return False
        return (body_size(c) / rng) >= 0.35
        
    signal = None
    entry = sl = tp = 0.0

    # BUY Signal logic
    if is_red(c_prev1) and is_green(c_curr):
        if c_curr['close'] > c_prev1['open'] and c_curr['open'] <= c_prev1['close']:
            if has_strong_body(c_curr):
                signal = "BUY"
                # pullback entry calculation
                entry = c_curr['low'] + candle_range(c_curr) * 0.5
                sl = c_curr['low'] - atr * 1.5
                tp = entry + atr * 2.0

    # SELL Signal logic
    if not signal and is_green(c_prev1) and is_red(c_curr):
        if c_curr['close'] < c_prev1['open'] and c_curr['open'] >= c_prev1['close']:
            if has_strong_body(c_curr):
                signal = "SELL"
                # pullback entry calculation
                entry = c_curr['high'] - candle_range(c_curr) * 0.5
                sl = c_curr['high'] + atr * 1.5
                tp = entry - atr * 2.0
                
    if not signal:
        return res
        
    return {
        "signal": signal,
        "entry": round(entry, 2),
        "sl": round(sl, 2),
        "tp": round(tp, 2),
        "price": round(entry, 2),
        "reason": "S20.9 - Candle Action Pullback 50%",
        "pattern": "S20.9",
        "sid": 20.9
    }
