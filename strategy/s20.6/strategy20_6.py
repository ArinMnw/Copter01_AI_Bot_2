"""
strategy20_6.py — S20.6 FVG Entry Standalone
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
แยกท่าย่อย S20.6 ออกมาจาก strategy20.py เพื่อให้ทำงานเป็นอิสระ (Standalone)
ประมวลผลการเข้า FVG Retest Models แบบเจาะลึก อิงจาก FVG.pdf (Deep Price Action)
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

def _find_fvg_retest_models(rates, atr, tf):
    """S20.6 FVG Retest Model (Deep Price Action)"""
    if len(rates) < 15:
        return None, None, None

    def is_green(c): return c and c['close'] > c['open']
    def is_red(c): return c and c['close'] < c['open']
    def body_size(c): return abs(c['close'] - c['open']) if c else 0
    def wick_top(c): return c['high'] - max(c['open'], c['close']) if c else 0
    def wick_bot(c): return min(c['open'], c['close']) - c['low'] if c else 0
    def candle_range(c): return c['high'] - c['low'] if c else 0

    c_curr = rates[-1]
    c_prev = rates[-2]
    
    trend_info = hhll_swing.get_trend_from_structure(tf)
    trend_strength = trend_info.get("strength", "") if trend_info else ""

    # ย้อนหา FVG ภายใน 40 แท่ง
    for i in range(len(rates) - 3, max(0, len(rates) - 40), -1):
        c1 = rates[i-2]
        c2 = rates[i-1] # Imbalance
        c3 = rates[i]

        fvg_type = None
        fvg_top = 0
        fvg_bot = 0

        # Detect FVG with ATR Momentum Expansion (Institutional Footprint)
        if is_green(c2) and c3['low'] > c1['high']:
            if body_size(c2) >= atr * 1.5:
                fvg_type = "BUY"
                fvg_top = c3['low']
                fvg_bot = c1['high']
        elif is_red(c2) and c3['high'] < c1['low']:
            if body_size(c2) >= atr * 1.5:
                fvg_type = "SELL"
                fvg_top = c1['low']
                fvg_bot = c3['high']

        if not fvg_type:
            continue

        touched = False
        gap_invalid = False
        made_new_high = False
        made_new_low = False
        
        first_touch_idx = -1
        made_new_high_after_touch = False
        made_new_low_after_touch = False
        
        # Check structure after FVG creation
        for k in range(i+1, len(rates) - 1):
            if fvg_type == "BUY":
                if rates[k]['high'] > c3['high']:
                    made_new_high = True
                    if touched:
                        made_new_high_after_touch = True
                if rates[k]['close'] < fvg_bot: # ปิดทะลุ GAP
                    gap_invalid = True
                    break
                if rates[k]['low'] <= fvg_top:
                    if not touched:
                        touched = True
                        first_touch_idx = k
            else:
                if rates[k]['low'] < c3['low']:
                    made_new_low = True
                    if touched:
                        made_new_low_after_touch = True
                if rates[k]['close'] > fvg_top: # ปิดทะลุ GAP
                    gap_invalid = True
                    break
                if rates[k]['high'] >= fvg_bot:
                    if not touched:
                        touched = True
                        first_touch_idx = k

        if gap_invalid:
            continue
            
        # [PDF Page 4, 7]: หากแท่งไม่ทำ High ใหม่ แสดงว่ามีแนวโน้มกวาดสภาพคล่องมา 2nd FVG
        if touched and first_touch_idx < len(rates) - 2:
            if fvg_type == "BUY" and not made_new_high_after_touch:
                continue # ข้าม 1st FVG Trap
            if fvg_type == "SELL" and not made_new_low_after_touch:
                continue # ข้าม 1st FVG Trap

        if fvg_type == "BUY":
            if not touched and c_prev['low'] <= fvg_top:
                touched = True
            
            if touched and is_green(c_prev):
                # [PDF Page 4]: รับแรง FVG แท่งเทียนต้องปิดเหนือ GAP
                if c_prev['close'] >= fvg_top:
                    c_p2 = rates[-3]
                    is_engulf = c_prev['close'] >= c_p2['high']
                    is_half_engulf = body_size(c_prev) > (body_size(c_p2) * 0.5)
                    is_pinbar = wick_bot(c_prev) > (body_size(c_prev) * 2)

                    # [PDF Page 8]: commitment ต้องดี (เนื้อเกินครึ่ง หรือเป็น Pin bar)
                    if is_engulf or is_half_engulf or is_pinbar:
                        # [PDF Page 6]: ต้องมีการทำไส้บนบ้าง ไม่งั้นเตรียมโดด Sell
                        if wick_top(c_prev) < atr * 0.02 and c_prev['close'] <= c_p2['high']:
                            return None, "S20.6.Blocked_NoTopWick_Trap", c_prev
                        
                        return "BUY", "S20.6.FVG_Entry", c_prev, c1, c3
                        
        else: # SELL
            if not touched and c_prev['high'] >= fvg_bot:
                touched = True
                
            if touched and is_red(c_prev):
                # [PDF Page 4]: แท่งที่ย้อนมารับ FVG ขา Sell ต้องปิดใต้ GAP
                if c_prev['close'] <= fvg_bot:
                    c_p2 = rates[-3]
                    is_engulf = c_prev['close'] <= c_p2['low']
                    is_half_engulf = body_size(c_prev) > (body_size(c_p2) * 0.5)
                    is_pinbar = wick_top(c_prev) > (body_size(c_prev) * 2)
                    
                    if is_engulf or is_half_engulf or is_pinbar:
                        # [PDF Page 6]: ต้องมีการทำไส้ล่างบ้าง
                        if wick_bot(c_prev) < atr * 0.02 and c_prev['close'] >= c_p2['low']:
                            return None, "S20.6.Blocked_NoBotWick_Trap", c_prev
                        
                        return "SELL", "S20.6.FVG_Entry", c_prev, c1, c3

    return None, None, None, None, None


def strategy_20_6(rates, tf="M5", dt_bkk=None) -> dict:
    if getattr(config, "S20_6_TF_ENABLED", {}).get(tf) is False:
        return {"signal": "WAIT", "reason": f"S20.6 is disabled for {tf}", "pattern": "S20.6", "sid": 20.6}

    if not _in_session(dt_bkk):
        return {"signal": "WAIT", "reason": "S20.6 - นอกเวลาทำการ", "pattern": "S20.6", "sid": 20.6}
        
    if rates is None or len(rates) < 40:
        return {"signal": "WAIT", "reason": "S20.6 - ข้อมูลไม่พอ (ตัองการ 40+ แท่ง)", "pattern": "S20.6", "sid": 20.6}

    atr = calc_atr(rates[:-1], 14) or 1.0

    signal = None
    res = {"signal": "WAIT", "reason": "", "pattern": "S20.6", "sid": 20.6}
    sub_pattern = None
    
    # 2) ค้นหา FVG Retest Models (S20.6)
    fvg_sig, fvg_pattern, anc_candle, fvg_c1, fvg_c3 = _find_fvg_retest_models(rates, atr, tf)
    
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
        
        if signal == "BUY":
            entry = c_prev1['close'] # Market order on close
            # Structure-based SL: Anchor low of the FVG impulse
            sl_raw = fvg_c1['low'] - (atr * 0.2)
        else:
            entry = c_prev1['close']
            # Structure-based SL: Anchor high of the FVG impulse
            sl_raw = fvg_c1['high'] + (atr * 0.2)
            
        sl = sl_raw
        
        low_pt = c_prev1['low']
        high_pt = c_prev1['high']
        
        if signal == "BUY":
            # Structure-based TP: Aim for the liquidity above the recent high
            highest_since_fvg = max([c['high'] for c in rates[-40:] if c['time'] > fvg_c3['time']])
            tp_raw = highest_since_fvg + (atr * 0.2)
            # Fallback to RR 1:1.5 if structural TP is too close
            if tp_raw < entry + (entry - sl) * 1.5:
                tp_raw = entry + (entry - sl) * 1.5
        else:
            # Structure-based TP: Aim for the liquidity below the recent low
            lowest_since_fvg = min([c['low'] for c in rates[-40:] if c['time'] > fvg_c3['time']])
            tp_raw = lowest_since_fvg - (atr * 0.2)
            # Fallback to RR 1:1.5 if structural TP is too close
            if tp_raw > entry - (sl - entry) * 1.5:
                tp_raw = entry - (sl - entry) * 1.5
                
        res.update({
            "signal": signal,
            "price": round(entry, 2),
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "tp": round(tp_raw, 2),
            "reason": f"S20.6 - {sub_pattern}",
            "pattern": sub_pattern,
            "sid": 20.6
        })
            
    return res
