"""
strategy20_6.py — S20.6 FVG Entry Standalone
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
แยกท่าย่อย S20.6 ออกมาจาก strategy20.py เพื่อให้ทำงานเป็นอิสระ (Standalone)
ใช้สำหรับประมวลผลการเข้า FVG Retest Models แบบเจาะลึก
"""

import config
import hhll_swing
from mt5_utils import calc_atr

def _in_session(dt_bkk) -> bool:
    """เช็ค Killzones (London/NY)"""
    if not getattr(config, "S20_SESSION_FILTER", False):
        return True
    if dt_bkk is None:
        return True
    cur = dt_bkk.time() if hasattr(dt_bkk, 'time') else dt_bkk
    sessions = getattr(config, "S20_SESSIONS", [("14:00", "18:00"), ("19:00", "23:00")])
    from datetime import time
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

def _find_fvg_retest_models(rates, atr):
    """S20.6 FVG Retest Model (อิงจาก FVG.pdf)"""
    if len(rates) < 10:
        return None, None, None

    def is_green(c): return c and c['close'] > c['open']
    def is_red(c): return c and c['close'] < c['open']
    def body_size(c): return abs(c['close'] - c['open']) if c else 0
    def wick_top(c): return c['high'] - max(c['open'], c['close']) if c else 0
    def wick_bot(c): return min(c['open'], c['close']) - c['low'] if c else 0

    c_curr = rates[-1]
    c_prev = rates[-2]

    # ย้อนหา FVG ภายใน 30 แท่ง
    for i in range(len(rates) - 3, max(0, len(rates) - 30), -1):
        c1 = rates[i-2]
        c2 = rates[i-1] # Imbalance
        c3 = rates[i]

        fvg_type = None
        fvg_top = 0
        fvg_bot = 0

        if is_green(c2) and c3['low'] > c1['high']:
            fvg_type = "BUY"
            fvg_top = c3['low']
            fvg_bot = c1['high']
        elif is_red(c2) and c3['high'] < c1['low']:
            fvg_type = "SELL"
            fvg_top = c1['low']
            fvg_bot = c3['high']

        if not fvg_type:
            continue

        touched = False
        gap_invalid = False
        
        for k in range(i+1, len(rates) - 1):
            if fvg_type == "BUY":
                if rates[k]['close'] < fvg_bot: # ปิดทะลุ GAP
                    gap_invalid = True
                    break
                if rates[k]['low'] <= fvg_top:
                    touched = True
            else:
                if rates[k]['close'] > fvg_top: # ปิดทะลุ GAP
                    gap_invalid = True
                    break
                if rates[k]['high'] >= fvg_bot:
                    touched = True

        if gap_invalid:
            continue

        if fvg_type == "BUY":
            if not touched and c_prev['low'] <= fvg_top:
                touched = True
            
            if touched and is_green(c_prev):
                # รับแรง FVG แท่งเทียนต้องปิดเหนือ GAP
                if c_prev['close'] >= fvg_top:
                    c_p2 = rates[-3]
                    is_engulf = c_prev['close'] >= c_p2['high']
                    is_half_engulf = body_size(c_prev) > (body_size(c_p2) * 0.5)

                    if is_engulf or is_half_engulf:
                        if wick_top(c_prev) < atr * 0.05:
                            return None, "S20.6.Blocked_NoTopWick", c_prev
                        return "BUY", "S20.6.FVG_Entry", c_prev
                        
        else: # SELL
            if not touched and c_prev['high'] >= fvg_bot:
                touched = True
                
            if touched and is_red(c_prev):
                if c_prev['close'] <= fvg_bot:
                    c_p2 = rates[-3]
                    is_engulf = c_prev['close'] <= c_p2['low']
                    is_half_engulf = body_size(c_prev) > (body_size(c_p2) * 0.5)
                    
                    if is_engulf or is_half_engulf:
                        if wick_bot(c_prev) < atr * 0.05:
                            return None, "S20.6.Blocked_NoBotWick", c_prev
                        return "SELL", "S20.6.FVG_Entry", c_prev

    return None, None, None


def strategy_20_6(rates, tf="M5", dt_bkk=None) -> dict:
    if not _in_session(dt_bkk):
        return {"signal": "WAIT", "reason": "S20.6 - นอกเวลาทำการ", "pattern": "S20.6", "sid": 20.6}
        
    if rates is None or len(rates) < 30:
        return {"signal": "WAIT", "reason": "S20.6 - ข้อมูลไม่พอ (ตัองการ 30+ แท่ง)", "pattern": "S20.6", "sid": 20.6}

    atr = calc_atr(rates[:-1], 14) or 1.0

    signal = None
    res = {"signal": "WAIT", "reason": "", "pattern": "S20.6", "sid": 20.6}
    sub_pattern = None
    
    # 2) ค้นหา FVG Retest Models (S20.6)
    fvg_sig, fvg_pattern, anc_candle = _find_fvg_retest_models(rates, atr)
    
    if fvg_sig:
        if not _trend_allows(fvg_sig, tf):
            res["signal"] = "WAIT"
            res["reason"] = f"S20.6 - สวน Strong Trend ({fvg_sig})"
            return res
            
        signal = fvg_sig
        sub_pattern = fvg_pattern
        c_prev1 = rates[-2]
        
        # ── Calculate Entry, SL, TP (Mimicking old strategy20.py) ──
        tf_max_wick = {"M1": 50.0, "M5": 310.0, "M15": 363.0, "M30": 621.0, "H1": 1200.0, "H4": 2100.0, "H12": 3500.0, "D1": 3390.0}
        base_wick = 310.0
        tf_scale = tf_max_wick.get(tf, base_wick) / base_wick
        
        entry_buffer = getattr(config, "S20_ENTRY_BUFFER", 0.0) * tf_scale * 0.01
        sl_2l2h = atr * 1.5
        
        fibo_run = min(7.044, 3.097) # capped as in old logic for anchor size
        
        # S20.6 never has "Solid" in sub_pattern, so it uses the 'else' branch
        if signal == "BUY":
            entry = c_prev1['low'] + entry_buffer
            sl_raw = c_prev1['low'] - sl_2l2h
        else:
            entry = c_prev1['high'] - entry_buffer
            sl_raw = c_prev1['high'] + sl_2l2h
            
        sl = sl_raw
        
        low_pt = c_prev1['low']
        high_pt = c_prev1['high']
        
        if signal == "BUY":
            tp_raw = sl_raw + ((high_pt - sl_raw) * fibo_run)
            tp_raw = max(tp_raw, entry + atr)
            sl = min(sl, entry - (atr * 0.2))
        else:
            tp_raw = sl_raw - ((sl_raw - low_pt) * fibo_run)
            tp_raw = min(tp_raw, entry - atr)
            sl = max(sl, entry + (atr * 0.2))
                
        res.update({
            "signal": signal,
            "price": round(entry, 2),
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "tp": round(tp_raw, 2),
            "reason": f"S20 - {sub_pattern}",
            "pattern": sub_pattern,
            "sid": 20.6
        })
            
    return res
