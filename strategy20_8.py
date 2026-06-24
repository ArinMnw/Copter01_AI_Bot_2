import config
from mt5_utils import calc_atr

def strategy_20_8(rates, tf_name: str, config=config) -> dict:
    """
    S20.8_Ultimate_2_Entry (ท่าไม้ตายอออิน4วิ 2 - Rejection & Small 2L/2H)
    - เน้นจับแท่ง Rejection บริเวณ High/Low (แท่งเขียว/แดง ที่ตันด้านใดด้านหนึ่ง)
    - เข้าเทรดเผื่อระยะ 390 จุด เพื่อกินไส้ (Wick Eating) ของแท่งถัดไป
    - SL ตัดขาดทุนสั้น 75-100 จุดจากฐาน เพื่อป้องกันท่าผีเสื้อ (Butterfly Trap)
    """
    res = {"signal": "WAIT", "reason": "", "pattern": "S20.8", "sid": 20.8}
    
    # We check active_strategies since we updated scanner.py to use it, but keep double check
    if not config.active_strategies.get(20.8, False):
        return res

    if len(rates) < 3:
        return res

    c = rates[-1]
    prev_c = rates[-2]

    body = abs(c['close'] - c['open'])
    total_len = c['high'] - c['low']
    
    if total_len == 0:
        return res

    upper_wick = c['high'] - max(c['open'], c['close'])
    lower_wick = min(c['open'], c['close']) - c['low']

    # เกณฑ์พิจารณาว่าเป็นแท่ง "ตัน" คือ ไส้ต้องน้อยกว่า 10% ของความยาวแท่ง หรือไม่เกิน 15 จุด
    max_wick_tol = max(total_len * 0.1, 15.0)
    
    # ห้ามเล่นแท่ง Engulfing เต็มแท่งที่ไร้ไส้ทั้งสองด้าน (เพราะจะไม่ย้อน)
    if upper_wick <= max_wick_tol and lower_wick <= max_wick_tol:
        return res

    # 1. ฝั่ง BUY: Rejection ที่ Low (ไม่มีไส้ล่าง)
    if lower_wick <= max_wick_tol and body > (total_len * 0.4):
        # ต้องทำตัวเป็น Local Low
        if c['low'] <= prev_c['low']:
            entry_buffer = 390.0 * 0.01
            sl_buffer = 100.0 * 0.01
            tp_buffer = 150.0 * 0.01
            
            entry = c['close'] - entry_buffer
            sl = c['low'] - sl_buffer
            tp = c['high'] + tp_buffer
            
            # ถ้า entry ต่ำกว่า sl แสดงว่าแท่งมันสั้นมากจน buffer ทะลุ SL แบบนี้ข้าม
            if entry > sl:
                return {
                    "signal": "BUY",
                    "entry": round(entry, 2),
                    "sl": round(sl, 2),
                    "tp": round(tp, 2),
                    "pattern": "2L_REJ",
                    "reason": "S20.8 - BUY Rejection Low",
                    "time": c['time'],
                    "sid": 20.8
                }

    # 2. ฝั่ง SELL: Rejection ที่ High (ไม่มีไส้บน)
    if upper_wick <= max_wick_tol and body > (total_len * 0.4):
        # ต้องทำตัวเป็น Local High
        if c['high'] >= prev_c['high']:
            entry_buffer = 390.0 * 0.01
            sl_buffer = 100.0 * 0.01
            tp_buffer = 150.0 * 0.01
            
            entry = c['close'] + entry_buffer
            sl = c['high'] + sl_buffer
            tp = c['low'] - tp_buffer
            
            if entry < sl:
                return {
                    "signal": "SELL",
                    "entry": round(entry, 2),
                    "sl": round(sl, 2),
                    "tp": round(tp, 2),
                    "pattern": "2H_REJ",
                    "reason": "S20.8 - SELL Rejection High",
                    "time": c['time'],
                    "sid": 20.8
                }

    return res
