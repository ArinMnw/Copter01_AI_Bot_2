"""
strategy20.py — S20 All in 4s (Hardcore Mode + VIP Enhancements)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sub-patterns (ท่าย่อยตามฉบับ All in 4s):
  S20.1.Defect: แท่งตำหนิที่ต้องเกิดที่ Swing High/Low ในรอบ 20 แท่งเท่านั้น
  S20.2.Small_2L / 2H: โครงสร้างย่อย กลับตัว 2L/2H ขนาดเล็ก
  S20.3.Solid: แท่งตันปฏิเสธราคา (Solid Momentum)

VIP Enhancements Added:
- Psychological Numbers (หลบ 0 และ 5)
- Fibo Targets: Wick Fill Target (1:1.5 RR)
- Strict No-Touch SL
- HTF FVG Liquidity Filter (D1/H4)
"""

from datetime import time
import config
import hhll_swing
from mt5_utils import calc_atr
import htf_fvg

def _in_session(dt_bkk) -> bool:
    """เช็ค Killzones (London/NY)"""
    if not getattr(config, "S20_SESSION_FILTER", False):
        return True
    if dt_bkk is None:
        return True
    cur = dt_bkk.time() if hasattr(dt_bkk, 'time') else dt_bkk
    sessions = getattr(config, "S20_SESSIONS", [("14:00", "18:00"), ("19:00", "23:00")])
    for start_str, end_str in sessions:
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        if time(sh, sm) <= cur < time(eh, em):
            return True
    return False

def _trend_allows(signal: str, tf: str) -> bool:
    """ห้ามเข้าสวน Strong Trend"""
    if not getattr(config, "S20_TREND_FILTER", False):
        return True
    trend_info = hhll_swing.get_trend_from_structure(tf)
    if not trend_info:
        return True
    trend = trend_info.get("trend", "UNKNOWN")
    strength = trend_info.get("strength", "")
    if signal == "BUY" and trend == "BEAR" and strength == "strong":
        return False
    if signal == "SELL" and trend == "BULL" and strength == "strong":
        return False
    return True

def _apply_psychological_number(price: float, is_buy: bool, is_tp: bool) -> float:
    """
    VIP Rule: Adjusts the price to end in 7 or 8. Avoids 0 and 5.
    Front-runs the retail stops.
    """
    if not getattr(config, "S20_USE_PSYCHOLOGICAL_NUMBERS", True):
        return price
        
    int_price = int(price)
    last_digit = int_price % 10
    
    offset = 0
    if last_digit in (0, 1, 2):
        offset = - (last_digit + 2)  # 0 -> -2 (ends in 8)
    elif last_digit in (3, 4, 5, 6):
        offset = (8 - last_digit)    # 5 -> +3 (ends in 8)
    elif last_digit == 9:
        offset = -1                  # 9 -> -1 (ends in 8)
        
    if last_digit == 7:
        offset = 0
        
    return float(int_price + offset) + (price - int_price)






def strategy_20(rates, tf="M5", dt_bkk=None) -> dict:
    if not _in_session(dt_bkk):
        return {"signal": "WAIT", "reason": "S20 - นอกเวลาทำการ", "pattern": "S20", "sid": 20}
        
    if rates is None or len(rates) < 20:
        return {"signal": "WAIT", "reason": "S20 - ข้อมูลไม่พอ (ตัองการ 20+ แท่ง)", "pattern": "S20", "sid": 20}

    atr = calc_atr(rates[:-1], 14) or 1.0

    signal = None
    res = {"signal": "WAIT", "reason": "", "pattern": "S20", "sid": 20}
    sub_pattern = None
    
    c_curr  = rates[-1]
    c_prev1 = rates[-2]
    c_prev2 = rates[-3]
    c_prev3 = rates[-4]

    def is_green(c): return c and c['close'] > c['open']
    def is_red(c): return c and c['close'] < c['open']
    def body_size(c): return abs(c['close'] - c['open']) if c else 0
    def wick_top(c): return c['high'] - max(c['open'], c['close']) if c else 0
    def wick_bot(c): return min(c['open'], c['close']) - c['low'] if c else 0

    # ── STAGE 1: Base Triggers (Strict High/Low Filter) ─────────────────
    recent_rates = rates[-20:]
    recent_high = max(r['high'] for r in recent_rates)
    recent_low  = min(r['low']  for r in recent_rates)
    
    is_swing_high = (c_curr['high'] >= recent_high or c_prev1['high'] >= recent_high)
    is_swing_low  = (c_curr['low'] <= recent_low or c_prev1['low'] <= recent_low)

    ref_bar = c_curr

    # 1. Defect Candle (S20.1.Defect)
    if not signal and (is_swing_high or is_swing_low):
        # BUY: Swing Low -> Previous is Red, Current is Green (Engulfs body, but leaves wick alone)
        if is_swing_low and is_red(c_prev1) and is_green(c_curr):
            if c_curr['close'] > c_prev1['open'] and c_curr['low'] > c_prev1['low']:
                signal, sub_pattern, ref_bar = "BUY", "S20.1.Defect", c_prev1
                
        # SELL: Swing High -> Previous is Green, Current is Red (Engulfs body, but leaves high wick alone)
        if is_swing_high and is_green(c_prev1) and is_red(c_curr):
            if c_curr['close'] < c_prev1['open'] and c_curr['high'] < c_prev1['high']:
                signal, sub_pattern, ref_bar = "SELL", "S20.1.Defect", c_prev1

    # 2. Small 2L / 2H Trap (S20.2.Small)
    if not signal:
        # BUY (2L): Green pushing up -> Red pulls back but doesn't break origin low -> Current Green
        if is_green(c_prev3) and is_green(c_prev2) and is_red(c_prev1) and is_green(c_curr):
            if c_prev1['low'] >= min(c_prev3['low'], c_prev2['low']):
                signal, sub_pattern, ref_bar = "BUY", "S20.2.Small_2L", c_prev1
                
        # SELL (2H): Red pushing down -> Green pulls back but doesn't break origin high -> Current Red
        if is_red(c_prev3) and is_red(c_prev2) and is_green(c_prev1) and is_red(c_curr):
            if c_prev1['high'] <= max(c_prev3['high'], c_prev2['high']):
                signal, sub_pattern, ref_bar = "SELL", "S20.2.Small_2H", c_prev1

    # 3. Solid Rejection (S20.3.Solid)
    if not signal and (is_swing_high or is_swing_low):
        # BUY: Green solid (no top wick) at Low
        if is_swing_low and is_green(c_curr) and wick_top(c_curr) < atr * 0.1:
            signal, sub_pattern, ref_bar = "BUY", "S20.3.Solid", c_curr
            
        # SELL: Red solid (no bot wick) at High
        if is_swing_high and is_red(c_curr) and wick_bot(c_curr) < atr * 0.1:
            signal, sub_pattern, ref_bar = "SELL", "S20.3.Solid", c_curr

    # 4. Pullback 80% (S20.4.Pullback80)
    # จากคัมภีร์เชิงแท่งเทียน: "แท่งสวนเทรนด์ปิดไม่คลุมเนื้อ โอกาสย้อนกลับ 80%"
    if not signal:
        # BUY: Trend UP. Red pulls down, Green tries to go up but fails to engulf Red's body.
        # Next candle pulls back DOWN to the wick. We Buy there.
        if is_swing_low and is_red(c_prev2) and is_green(c_prev1):
            if c_prev1['close'] < c_prev2['open']:
                signal, sub_pattern, ref_bar = "BUY", "S20.4.Pullback80", c_prev1
                
        # SELL: Trend DOWN. Green pulls up, Red tries to go down but fails to engulf Green's body.
        # Next candle pulls back UP to the wick. We Sell there.
        if is_swing_high and is_green(c_prev2) and is_red(c_prev1):
            if c_prev1['close'] > c_prev2['open']:
                signal, sub_pattern, ref_bar = "SELL", "S20.4.Pullback80", c_prev1


    if not signal:
        return res
        
    # --- [NEW] D1/H4 HTF FVG Liquidity Filter ---
    # บอทจะเช็คว่าตำแหน่งที่เกิดสัญญาณ อยู่ใน FVG ของ D1 หรือ H4 หรือไม่
    # ถ้าไม่อยู่ ถือว่าเป็น Liquidity Trap
    if getattr(config, "S20_HTF_FVG_FILTER", False):
        htf_tfs = getattr(config, "S20_HTF_TFS", ["D1", "H4"])
        check_price = ref_bar['low'] if signal == "BUY" else ref_bar['high']
        check_time = int(ref_bar['time'])
        if not htf_fvg.is_price_in_htf_fvg(check_price, signal, htf_tfs, at_time=check_time):
            return {"signal": "WAIT", "reason": f"S20 - Liquidity Trap (Not in D1/H4 FVG)"}
            
    # --- ────────────────────────────────────── ---

    # ── Trend Filter ──
    if tf and not _trend_allows(signal, tf):
        res["reason"] = f"S20: Blocked by Counter-Trend [{tf}]"
        return res

    # ── Calculate Entry, SL, TP ──
    tf_max_wick = {"M1": 50.0, "M5": 310.0, "M15": 363.0, "M30": 621.0, "H1": 1200.0, "H4": 2100.0, "H12": 3500.0, "D1": 3390.0}
    base_wick = 310.0
    tf_scale = tf_max_wick.get(tf, base_wick) / base_wick
    
    entry_buffer = getattr(config, "S20_ENTRY_BUFFER", 0.0) * tf_scale * 0.01
    sl_2l2h = atr * 1.5
    
    fibo_run = 7.044
    fibo_krh2 = 3.097
    if "Defect" in sub_pattern:
        fibo_run = 2.0  # Wick fill target instead of deep run
        
    if "Pullback80" in sub_pattern:
        fibo_run = 1.0  # 1:1 RR to capture the 80% short pullback
        
    if "Small" in sub_pattern:
        fibo_run = 1.5  # Wick fill target
        
    if getattr(config, "S20_DYNAMIC_FIBO", True):
        anchor_size = abs(ref_bar['high'] - ref_bar['low'])
        if anchor_size > (atr * 1.5):
            fibo_run = min(fibo_run, 3.097)  # Cap to KRH2 if anchor is too big
    
    fibo_levels = {}

    # 1. Entry: For Defect & 2L/2H, entry is at the WICK of the anchor
    # For Solid, it's 50% retrace of the body
    if "Solid" in sub_pattern:
        entry = (ref_bar['open'] + ref_bar['close']) / 2
        sl_raw = ref_bar['low'] if signal == "BUY" else ref_bar['high']
    else:
        if signal == "BUY":
            entry = ref_bar['low'] + entry_buffer
            sl_raw = ref_bar['low'] - sl_2l2h
        else:
            entry = ref_bar['high'] - entry_buffer
            sl_raw = ref_bar['high'] + sl_2l2h
            
    # "No Touch Rule" - Strict SL
    sl = sl_raw

    # 2. Fibo Targets
    low_pt = ref_bar['low']
    high_pt = ref_bar['high']
    
    if signal == "BUY":
        tp_raw = sl_raw + ((high_pt - sl_raw) * fibo_run)
    else:
        tp_raw = sl_raw - ((sl_raw - low_pt) * fibo_run)

    # 3. Modifiers (Psychological Numbers)
    if getattr(config, "S20_USE_PSYCHOLOGICAL_NUMBERS", True):
        entry = _apply_psychological_number(entry, is_buy=(signal=="BUY"), is_tp=False)
        tp_raw = _apply_psychological_number(tp_raw, is_buy=(signal=="BUY"), is_tp=True)

    # 4. Limit minimum RR
    if signal == "BUY":
        tp_raw = max(tp_raw, entry + atr)
        sl = min(sl, entry - (atr*0.2))
    else:
        tp_raw = min(tp_raw, entry - atr)
        sl = max(sl, entry + (atr*0.2))

    res_out = {
        "signal": signal,
        "entry": round(entry, 2),
        "sl": round(sl, 2),
        "tp": round(tp_raw, 2),
        "reason": f"S20 - {sub_pattern}",
        "pattern": sub_pattern,
        "sid": 20.6 if sub_pattern and "S20.6" in sub_pattern else 20
    }
    
    if fibo_levels:
        res_out["zone_meta"] = fibo_levels
        
    return res_out
