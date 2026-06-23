"""
strategy20_5.py — S20.5 Fibo Standalone
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
แยกท่าย่อย S20.5 ออกมาจาก strategy20.py เพื่อให้ทำงานเป็นอิสระ (Standalone)
ใช้สำหรับประมวลผลการเข้า Fibo Entry Models แบบเจาะลึก
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

def _find_fibo_models(rates, atr):
    """Scan history to find Fibo Sequence Models (Hit 1 test 50, Hit 2 test 50, 3 Test 1, Run Test 2)"""
    if len(rates) < 30:
        return None, None, None
        
    def is_green(c): return c and c['close'] > c['open']
    def is_red(c): return c and c['close'] < c['open']
    def body_size(c): return abs(c['close'] - c['open']) if c else 0
    def wick_top(c): return c['high'] - max(c['open'], c['close']) if c else 0
    def wick_bot(c): return min(c['open'], c['close']) - c['low'] if c else 0

    # Scan backwards to find the most recent valid sequence
    for i in range(len(rates) - 3, max(0, len(rates) - 30), -1):
        c_pre = rates[i-1]
        c_anc = rates[i]
        c_con = rates[i+1]
        
        anchor_type = None
        
        # BUY Anchor: Red -> Green (Engulf/Defect) -> Green (Confirm)
        if is_red(c_pre) and is_green(c_anc) and is_green(c_con):
            is_engulf = c_anc['close'] > c_pre['high']
            is_defect = (wick_top(c_anc) > body_size(c_anc)) or (c_anc['close'] > c_pre['close'] and c_anc['close'] <= c_pre['high'])
            if is_engulf or is_defect:
                anchor_type = "BUY"
                
        # SELL Anchor: Green -> Red (Engulf/Defect) -> Red (Confirm)
        elif is_green(c_pre) and is_red(c_anc) and is_red(c_con):
            is_engulf = c_anc['close'] < c_pre['low']
            is_defect = (wick_bot(c_anc) > body_size(c_anc)) or (c_anc['close'] < c_pre['close'] and c_anc['close'] >= c_pre['low'])
            if is_engulf or is_defect:
                anchor_type = "SELL"
                
        if not anchor_type:
            continue
            
        pt_0 = c_anc['low'] if anchor_type == "BUY" else c_anc['high']
        pt_1 = c_anc['high'] if anchor_type == "BUY" else c_anc['low']
        anchor_size = abs(pt_1 - pt_0)
        
        if anchor_type == "BUY":
            fibo_57 = pt_0 + (anchor_size * 0.57)
            fibo_40 = pt_0 + (anchor_size * 0.40)
            fibo_1 = pt_0 + (anchor_size * 1.617)
            fibo_2 = pt_0 + (anchor_size * 3.097)
            fibo_3 = pt_0 + (anchor_size * 5.165)
            fibo_run = pt_0 + (anchor_size * 7.044)
        else:
            fibo_57 = pt_0 - (anchor_size * 0.57)
            fibo_40 = pt_0 - (anchor_size * 0.40)
            fibo_1 = pt_0 - (anchor_size * 1.617)
            fibo_2 = pt_0 - (anchor_size * 3.097)
            fibo_3 = pt_0 - (anchor_size * 5.165)
            fibo_run = pt_0 - (anchor_size * 7.044)
            
        hit_1 = False
        hit_2 = False
        hit_3 = False
        hit_run = False
        failed = False
        has_pullback = False
        
        for k in range(i+1, len(rates)):
            bar = rates[k]
            if anchor_type == "BUY":
                if is_red(bar): has_pullback = True
                if bar['close'] < pt_0: # หลุด 0 คือพัง
                    failed = True
                    break
                if bar['high'] >= fibo_run: hit_run = True
                elif bar['high'] >= fibo_3: hit_3 = True
                elif bar['high'] >= fibo_2: hit_2 = True
                elif bar['high'] >= fibo_1: hit_1 = True
            else:
                if is_green(bar): has_pullback = True
                if bar['close'] > pt_0: # หลุด 0 คือพัง
                    failed = True
                    break
                if bar['low'] <= fibo_run: hit_run = True
                elif bar['low'] <= fibo_3: hit_3 = True
                elif bar['low'] <= fibo_2: hit_2 = True
                elif bar['low'] <= fibo_1: hit_1 = True
                    
        if failed:
            continue
            
        # Check rejection on the last closed candle
        c_p1 = rates[-2]
        
        is_testing_50 = False
        is_testing_2_after_run = False
        is_testing_1_after_3 = False
        
        if anchor_type == "BUY":
            # Test 50-60% Zone (0.4-0.57) - Include KRL (0) check for 90% Win Rate Setup
            touched_50 = (c_p1['low'] <= fibo_57 + (atr * 0.2))
            stood_50 = (c_p1['close'] >= fibo_40 - (atr * 0.2))
            touched_krl = (c_p1['low'] <= pt_0 + (atr * 0.5))  # Deep pullback down to KRL
            is_reject = (wick_bot(c_p1) > body_size(c_p1))
            
            if touched_50 and stood_50 and is_reject:
                is_testing_50 = True
                
            # Test 2 after RUN (Mango Root Check)
            touched_2 = (c_p1['low'] <= fibo_2 + (atr * 0.2))
            stood_2 = (c_p1['close'] >= fibo_2 - (atr * 0.2))
            if hit_run and touched_2:
                if stood_2 and is_reject:
                    is_testing_2_after_run = True
                elif c_p1['close'] < fibo_2:
                    return None, "S20.5.Blocked_Mango_Root", None # ถ้ายืน 2 ไม่ได้ ไปคุยกับรากมะม่วง (Mango Root Fall)
                    
            # RUN Test 1 (Falling Knife Warning)
            touched_1 = (c_p1['low'] <= fibo_1 + (atr * 0.2))
            if hit_run and touched_1 and c_p1['close'] < fibo_2:
                return None, "S20.5.Blocked_RUN_Test1_HeavyDump", None # เจอเทหนักอย่าหาซ้อน
                
            # Test 1 after 3
            stood_1 = (c_p1['close'] >= fibo_1 - (atr * 0.2))
            if hit_3 and not hit_run and touched_1 and stood_1 and is_reject:
                is_testing_1_after_3 = True
                
        else:
            # Test 50-60% Zone (0.4-0.57) - Include KRL (0) check for 90% Win Rate Setup
            touched_50 = (c_p1['high'] >= fibo_57 - (atr * 0.2))
            stood_50 = (c_p1['close'] <= fibo_40 + (atr * 0.2))
            touched_krl = (c_p1['high'] >= pt_0 - (atr * 0.5))
            is_reject = (wick_top(c_p1) > body_size(c_p1))
            
            if touched_50 and stood_50 and is_reject:
                is_testing_50 = True
                
            # Test 2 after RUN (Mango Root Check)
            touched_2 = (c_p1['high'] >= fibo_2 - (atr * 0.2))
            stood_2 = (c_p1['close'] <= fibo_2 + (atr * 0.2))
            if hit_run and touched_2:
                if stood_2 and is_reject:
                    is_testing_2_after_run = True
                elif c_p1['close'] > fibo_2:
                    return None, "S20.5.Blocked_Mango_Root", None # ถ้ายืน 2 ไม่ได้ ไปคุยกับรากมะม่วง (Mango Root Fall)
                    
            # RUN Test 1 (Falling Knife Warning)
            touched_1 = (c_p1['high'] >= fibo_1 - (atr * 0.2))
            if hit_run and touched_1 and c_p1['close'] > fibo_2:
                return None, "S20.5.Blocked_RUN_Test1_HeavyDump", None # เจอเทหนักอย่าหาซ้อน
                
            # Test 1 after 3
            stood_1 = (c_p1['close'] <= fibo_1 + (atr * 0.2))
            if hit_3 and not hit_run and touched_1 and stood_1 and is_reject:
                is_testing_1_after_3 = True

        if is_testing_2_after_run:
            return anchor_type, "S20.5.Fibo_Entry_RunTest2", c_anc
        elif is_testing_1_after_3:
            return anchor_type, "S20.5.Fibo_Entry_3Test1", c_anc
        elif is_testing_50 and not hit_run and not hit_3:
            if hit_2:
                return anchor_type, "S20.5.Fibo_Entry_Hit2_Deep" if touched_krl else "S20.5.Fibo_Entry_Hit2", c_anc
            elif hit_1:
                return anchor_type, "S20.5.Fibo_Entry_Hit1", c_anc

        # --- VIP Rule: Straight Line to 3 Invalidation (PDF Page 15) ---
        if hit_3 and not has_pullback:
            return None, "S20.5.Blocked_StraightTo3", None # ถ้าขึ้นเป็นเส้นตรงเลย 3 จะเล่นไม่ได้ (Straight Line to 3)

    return None, None, None


def strategy_20_5(rates, tf="M5", dt_bkk=None) -> dict:
    if not _in_session(dt_bkk):
        return {"signal": "WAIT", "reason": "S20.5 - นอกเวลาทำการ", "pattern": "S20.5", "sid": 20.5}
        
    if rates is None or len(rates) < 30:
        return {"signal": "WAIT", "reason": "S20.5 - ข้อมูลไม่พอ (ตัองการ 30+ แท่ง)", "pattern": "S20.5", "sid": 20.5}

    atr = calc_atr(rates[:-1], 14) or 1.0

    signal = None
    res = {"signal": "WAIT", "reason": "", "pattern": "S20.5", "sid": 20.5}
    sub_pattern = None
    
    # 1) ค้นหา Fibo Entry Models ก่อน
    fb_sig, fb_pattern, anc_candle = _find_fibo_models(rates, atr)
    
    if fb_sig:
        if not _trend_allows(fb_sig, tf):
            res["signal"] = "WAIT"
            res["reason"] = f"S20.5 - สวน Strong Trend ({fb_sig})"
            return res
            
        signal = fb_sig
        sub_pattern = fb_pattern
        c_prev1 = rates[-2]
        
        # Calculate SL / TP
        if signal == "BUY":
            entry = rates[-1]['open']
            sl = c_prev1['low'] - (atr * getattr(config, "SL_ATR_MULT", 2.0))
            tp_raw = entry + ((entry - sl) * 1.5)
        else:
            entry = rates[-1]['open']
            sl = c_prev1['high'] + (atr * getattr(config, "SL_ATR_MULT", 2.0))
            tp_raw = entry - ((sl - entry) * 1.5)
            
        fibo_levels = {}
        if anc_candle:
            p0 = anc_candle['low'] if signal=="BUY" else anc_candle['high']
            p1 = anc_candle['high'] if signal=="BUY" else anc_candle['low']
            sz = abs(p1 - p0)
            if signal == "BUY":
                fibo_levels = {
                    "0": p0, "100": p1, "161.8": p0 + sz*1.618, "261.8": p0 + sz*2.618, "423.6": p0 + sz*4.236
                }
            else:
                fibo_levels = {
                    "0": p0, "100": p1, "161.8": p0 - sz*1.618, "261.8": p0 - sz*2.618, "423.6": p0 - sz*4.236
                }
                
        res.update({
            "signal": signal,
            "price": round(entry, 2),
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "tp": round(tp_raw, 2),
            "reason": f"S20.5 - {sub_pattern}",
            "pattern": sub_pattern,
            "sid": 20.5
        })
        
        if fibo_levels:
            res["zone_meta"] = fibo_levels
            
    return res
