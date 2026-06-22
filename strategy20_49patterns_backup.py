import config

def scan_s20_signals(rates, tf=None, dt_bkk=None):
    """
    Backup file: The original 49 sub-patterns logic before the Pipeline Refactoring.
    This file is kept for historical reference in Git.
    """
    res = {"signal": "WAIT", "reason": ""}

    if len(rates) < 5:
        return res

    sub_cfg = getattr(config, "S20_SUB_CONFIG", {})
    
    c_prev3 = rates[-4] if len(rates) >= 4 else None
    c_prev2 = rates[-3] if len(rates) >= 3 else None
    c_prev1 = rates[-2] if len(rates) >= 2 else None
    c_curr  = rates[-1] if len(rates) >= 1 else None

    def is_green(c): return c and c['close'] > c['open']
    def is_red(c): return c and c['close'] < c['open']
    def body_size(c): return abs(c['close'] - c['open']) if c else 0
    def wick_top(c): return c['high'] - max(c['open'], c['close']) if c else 0
    def wick_bot(c): return min(c['open'], c['close']) - c['low'] if c else 0
    
    atr = 1.0 # placeholder
    solid_tol = atr * 0.05

    signal = None
    sub_pattern = None
    ref_bar = c_curr

    # [S20.1] Classic 2-Bar (กลับตัวสมบูรณ์ ปิดคลุมไส้)
    if not signal and sub_cfg.get("S20_1_CLASSIC", True):
        if is_red(c_prev1) and is_green(c_curr) and c_curr['close'] > c_prev1['high']: 
            signal, sub_pattern, ref_bar = "BUY", "S20.1", c_curr
        elif is_green(c_prev1) and is_red(c_curr) and c_curr['close'] < c_prev1['low']: 
            signal, sub_pattern, ref_bar = "SELL", "S20.1", c_curr

    # [S20.2] Wick Fill & Reject
    if not signal and sub_cfg.get("S20_2_WICK_FILL", True):
        if is_red(c_curr) and is_green(c_prev1) and c_curr['close'] < c_prev1['open'] and c_curr['close'] > c_prev1['low']:
            signal, sub_pattern, ref_bar = "BUY", "S20.2", c_prev1  
        elif is_green(c_curr) and is_red(c_prev1) and c_curr['close'] > c_prev1['open'] and c_curr['close'] < c_prev1['high']:
            signal, sub_pattern, ref_bar = "SELL", "S20.2", c_prev1

    # [S20.3] Solid Momentum
    if not signal and sub_cfg.get("S20_3_SOLID", True):
        if is_green(c_curr) and (c_curr['high'] - c_curr['close']) <= solid_tol:
            signal, sub_pattern, ref_bar = "BUY", "S20.3", c_curr
        elif is_red(c_curr) and (c_curr['close'] - c_curr['low']) <= solid_tol:
            signal, sub_pattern, ref_bar = "SELL", "S20.3", c_curr

    # [S20.4] Small 2L-2H (ท่าผีเสื้อ/ย่อสั้น)
    if not signal and sub_cfg.get("S20_4_SMALL_2L2H", True) and len(rates) >= 3:
        if is_green(c_prev2) and is_red(c_prev1) and is_green(c_curr) and c_prev1['low'] >= c_prev2['low'] and c_curr['close'] > c_prev1['high']:
            signal, sub_pattern, ref_bar = "BUY", "S20.4", c_curr
        if is_red(c_prev2) and is_green(c_prev1) and is_red(c_curr) and c_prev1['high'] <= c_prev2['high'] and c_curr['close'] < c_prev1['low']:
            signal, sub_pattern, ref_bar = "SELL", "S20.4", c_curr

    # [S20.5] LQ Sweep
    if not signal and sub_cfg.get("S20_5_LQ_SWEEP", True):
        signal, sub_pattern, ref_bar = None, "S20.5", c_curr # Placeholder logic
        
    # [S20.6] FVG Retest & Reject
    if not signal and sub_cfg.get("S20_6_FVG_RETEST", True):
        signal, sub_pattern, ref_bar = None, "S20.6", c_curr

    # [S20.7] Doji at Structure Break
    if not signal and sub_cfg.get("S20_7_DOJI_BREAK", True):
        signal, sub_pattern, ref_bar = None, "S20.7", c_curr

    # [S20.8] Candlestick Divergence
    if not signal and sub_cfg.get("S20_8_DIVERGENCE", True):
        signal, sub_pattern, ref_bar = None, "S20.8", c_curr

    # [S20.9] Trap Engulfing Return
    if not signal and sub_cfg.get("S20_9_TRAP_ENGULF", True):
        signal, sub_pattern, ref_bar = None, "S20.9", c_curr

    # [S20.10] Fibo Anchor 138-161 Reverse
    if not signal and sub_cfg.get("S20_10", True):
        if is_green(c_prev1) and wick_top(c_curr) > body_size(c_curr) * 2 and is_red(c_curr):
            signal, sub_pattern, ref_bar = "SELL", "S20.10", c_curr
        elif is_red(c_prev1) and wick_bot(c_curr) > body_size(c_curr) * 2 and is_green(c_curr):
            signal, sub_pattern, ref_bar = "BUY", "S20.10", c_curr

    # [S20.11] 2L KRL Base
    if not signal and sub_cfg.get("S20_11", True):
        if c_curr['low'] >= c_prev3['low'] and c_curr['low'] <= c_prev3['low'] + (atr * 0.2) and is_green(c_curr):
            signal, sub_pattern, ref_bar = "BUY", "S20.11", c_curr
        elif c_curr['high'] <= c_prev3['high'] and c_curr['high'] >= c_prev3['high'] - (atr * 0.2) and is_red(c_curr):
            signal, sub_pattern, ref_bar = "SELL", "S20.11", c_curr

    # [S20.12] Origin Retest
    if not signal and sub_cfg.get("S20_12", True):
        if body_size(c_prev2) < (atr * 0.2) and is_green(c_curr) and c_curr['low'] <= c_prev2['low']:
            signal, sub_pattern, ref_bar = "BUY", "S20.12", c_curr
        elif body_size(c_prev2) < (atr * 0.2) and is_red(c_curr) and c_curr['high'] >= c_prev2['high']:
            signal, sub_pattern, ref_bar = "SELL", "S20.12", c_curr

    # [S20.13] Fake Pullback (3-6 Candles)
    if not signal and sub_cfg.get("S20_13", True):
        if is_green(c_curr) and all(is_red(r) for r in rates[-5:-1]):
            signal, sub_pattern, ref_bar = "BUY", "S20.13", c_curr
        elif is_red(c_curr) and all(is_green(r) for r in rates[-5:-1]):
            signal, sub_pattern, ref_bar = "SELL", "S20.13", c_curr

    # [S20.14] DM/SP Trap Repeated Structure
    if not signal and sub_cfg.get("S20_14", True):
        if is_red(c_prev2) and is_green(c_prev1) and is_red(c_curr) and c_curr['close'] < c_prev2['low']:
            signal, sub_pattern, ref_bar = "SELL", "S20.14", c_curr
        elif is_green(c_prev2) and is_red(c_prev1) and is_green(c_curr) and c_curr['close'] > c_prev2['high']:
            signal, sub_pattern, ref_bar = "BUY", "S20.14", c_curr

    # [S20.15] Solid Candle Acceleration
    if not signal and sub_cfg.get("S20_15", True):
        if is_green(c_curr) and wick_top(c_curr) < (atr * 0.05) and body_size(c_curr) > atr:
            signal, sub_pattern, ref_bar = "BUY", "S20.15", c_curr
        elif is_red(c_curr) and wick_bot(c_curr) < (atr * 0.05) and body_size(c_curr) > atr:
            signal, sub_pattern, ref_bar = "SELL", "S20.15", c_curr

    # [S20.16] Defect 3-Candle Retrace
    if not signal and sub_cfg.get("S20_16", True):
        if is_green(c_prev2) and is_red(c_prev1) and is_green(c_curr) and c_curr['close'] > c_prev2['high']:
            signal, sub_pattern, ref_bar = "BUY", "S20.16", c_curr
        elif is_red(c_prev2) and is_green(c_prev1) and is_red(c_curr) and c_curr['close'] < c_prev2['low']:
            signal, sub_pattern, ref_bar = "SELL", "S20.16", c_curr

    # [S20.17] Wick Fill Fail
    if not signal and sub_cfg.get("S20_17", True):
        if is_green(c_prev1) and is_red(c_curr) and c_curr['low'] < c_prev1['low'] and c_curr['close'] > c_prev1['low']:
            signal, sub_pattern, ref_bar = "BUY", "S20.17", c_curr
        elif is_red(c_prev1) and is_green(c_curr) and c_curr['high'] > c_prev1['high'] and c_curr['close'] < c_prev1['high']:
            signal, sub_pattern, ref_bar = "SELL", "S20.17", c_curr

    # [S20.18] 2H/2L Reversal FVG Retest
    if not signal and sub_cfg.get("S20_18", True):
        if c_curr['low'] <= c_prev3['low'] and c_curr['close'] > c_prev3['low'] and is_green(c_curr):
            signal, sub_pattern, ref_bar = "BUY", "S20.18", c_curr
        elif c_curr['high'] >= c_prev3['high'] and c_curr['close'] < c_prev3['high'] and is_red(c_curr):
            signal, sub_pattern, ref_bar = "SELL", "S20.18", c_curr

    # [S20.19] Continuous SP FVG Trap
    if not signal and sub_cfg.get("S20_19", True):
        if is_red(c_prev1) and is_green(c_curr) and c_curr['close'] > c_prev1['high'] and body_size(c_curr) > atr:
            signal, sub_pattern, ref_bar = "BUY", "S20.19", c_curr
        elif is_green(c_prev1) and is_red(c_curr) and c_curr['close'] < c_prev1['low'] and body_size(c_curr) > atr:
            signal, sub_pattern, ref_bar = "SELL", "S20.19", c_curr

    # [S20.20] Anchoring on Defect Shift Target
    if not signal and sub_cfg.get("S20_20", True):
        if is_green(c_curr) and is_red(c_prev1) and c_curr['close'] > c_prev1['high'] and body_size(c_prev1) < atr*0.5:
            signal, sub_pattern, ref_bar = "BUY", "S20.20", c_curr
        elif is_red(c_curr) and is_green(c_prev1) and c_curr['close'] < c_prev1['low'] and body_size(c_prev1) < atr*0.5:
            signal, sub_pattern, ref_bar = "SELL", "S20.20", c_curr

    # [S20.21] Base of Bull Fibo 0.0 Level Buy
    if not signal and sub_cfg.get("S20_21", True):
        if is_green(c_curr) and c_curr['low'] <= c_prev1['low'] and c_curr['close'] > c_prev1['high']:
            signal, sub_pattern, ref_bar = "BUY", "S20.21", c_curr

    # [S20.22] KRH2 Breakdown Reversal
    if not signal and sub_cfg.get("S20_22", True):
        if is_red(c_curr) and c_curr['high'] >= c_prev1['high'] and c_curr['close'] < c_prev1['low']:
            signal, sub_pattern, ref_bar = "SELL", "S20.22", c_curr

    # [S20.23] Solid Candle Reversal
    if not signal and sub_cfg.get("S20_23", True):
        if is_green(c_prev1) and wick_top(c_prev1) == 0 and is_red(c_curr) and c_curr['close'] < c_prev1['low']:
            signal, sub_pattern, ref_bar = "SELL", "S20.23", c_curr
        elif is_red(c_prev1) and wick_bot(c_prev1) == 0 and is_green(c_curr) and c_curr['close'] > c_prev1['high']:
            signal, sub_pattern, ref_bar = "BUY", "S20.23", c_curr

    # [S20.24] Fake SW at FVG
    if not signal and sub_cfg.get("S20_24", True):
        if is_green(c_prev2) and is_red(c_prev1) and is_red(c_curr) and c_curr['close'] < c_prev2['low']:
            signal, sub_pattern, ref_bar = "SELL", "S20.24", c_curr

    # [S20.25] Invalid Test at FVG
    if not signal and sub_cfg.get("S20_25", True):
        if is_red(c_prev1) and is_red(c_curr) and c_curr['close'] < c_prev1['low'] and body_size(c_curr) > atr:
            signal, sub_pattern, ref_bar = "SELL", "S20.25", c_curr

    # [S20.26] 50% Body Retracement
    if not signal and sub_cfg.get("S20_26", True):
        mid_body = (c_prev2['open'] + c_prev2['close']) / 2 if c_prev2 else 0
        if is_green(c_prev2) and is_red(c_prev1) and c_curr['low'] <= mid_body and is_green(c_curr):
            signal, sub_pattern, ref_bar = "BUY", "S20.26", c_curr
        elif is_red(c_prev2) and is_green(c_prev1) and c_curr['high'] >= mid_body and is_red(c_curr):
            signal, sub_pattern, ref_bar = "SELL", "S20.26", c_curr

    # [S20.27] Momentum Continuation Rule
    if not signal and sub_cfg.get("S20_27", True):
        if is_green(c_prev1) and is_green(c_curr) and c_curr['close'] > c_prev1['high']:
            signal, sub_pattern, ref_bar = "BUY", "S20.27", c_curr
        elif is_red(c_prev1) and is_red(c_curr) and c_curr['close'] < c_prev1['low']:
            signal, sub_pattern, ref_bar = "SELL", "S20.27", c_curr

    # [S20.28] H12/D1 2L Long Wick Confirmation
    if not signal and sub_cfg.get("S20_28", True):
        if is_green(c_curr) and wick_bot(c_curr) > body_size(c_curr) * 2 and c_curr['low'] <= c_prev2['low']:
            signal, sub_pattern, ref_bar = "BUY", "S20.28", c_curr

    # [S20.29] 2H Fails to Break Low
    if not signal and sub_cfg.get("S20_29", True):
        if is_red(c_prev1) and c_curr['low'] >= c_prev1['low'] and is_green(c_curr):
            signal, sub_pattern, ref_bar = "BUY", "S20.29", c_curr

    # [S20.30] No Touch Clear Candle Rule
    if not signal and sub_cfg.get("S20_30", True):
        if is_green(c_prev2) and wick_bot(c_prev2) > body_size(c_prev2) and c_curr['low'] <= c_prev2['low']:
            signal, sub_pattern, ref_bar = "SELL", "S20.30", c_curr
        elif is_red(c_prev2) and wick_top(c_prev2) > body_size(c_prev2) and c_curr['high'] >= c_prev2['high']:
            signal, sub_pattern, ref_bar = "BUY", "S20.30", c_curr

    # [S20.31] 2L Fake Trap
    if not signal and sub_cfg.get("S20_31", True):
        if is_green(c_curr) and c_curr['low'] < c_prev1['low'] and c_curr['close'] > c_prev1['low']:
            signal, sub_pattern, ref_bar = "BUY", "S20.31", c_curr

    # [S20.32] No Body Close on Support
    if not signal and sub_cfg.get("S20_32", True):
        if is_red(c_curr) and c_curr['close'] < c_prev2['low'] and body_size(c_curr) > atr * 0.5:
            signal, sub_pattern, ref_bar = "SELL", "S20.32", c_curr

    # [S20.33] TF Divergence Retracement
    if not signal and sub_cfg.get("S20_33", True):
        if is_green(c_curr) and is_red(c_prev1) and c_curr['close'] < c_prev1['high'] and c_curr['high'] > c_prev1['high']:
            signal, sub_pattern, ref_bar = "SELL", "S20.33", c_curr

    # [S20.34] D1/H12 Divergence
    if not signal and sub_cfg.get("S20_34", True):
        if is_red(c_prev1) and is_green(c_curr) and wick_top(c_curr) > body_size(c_curr):
            signal, sub_pattern, ref_bar = "BUY", "S20.34", c_curr

    # [S20.35] ATH Magic Number 7 Limit
    if not signal and sub_cfg.get("S20_35", True):
        if c_curr['close'] % 10 >= 7 and is_green(c_curr) and wick_top(c_curr) > 0:
            signal, sub_pattern, ref_bar = "SELL", "S20.35", c_curr

    # [S20.36] 3-Step Structure Fakeout
    if not signal and sub_cfg.get("S20_36", True):
        if is_red(c_curr) and c_curr['high'] <= c_prev3['high'] and c_curr['close'] < c_prev1['low']:
            signal, sub_pattern, ref_bar = "SELL", "S20.36", c_curr

    # [S20.37] Origin 3-Point Reference
    if not signal and sub_cfg.get("S20_37", True):
        if is_red(c_prev1) and body_size(c_prev1) < atr*0.2 and c_curr['low'] <= c_prev1['low'] and is_green(c_curr):
            signal, sub_pattern, ref_bar = "BUY", "S20.37", c_curr

    # [S20.38] LQ Overlap FVG Filter
    if not signal and sub_cfg.get("S20_38", True):
        if is_red(c_curr) and body_size(c_curr) > atr * 2 and c_curr['close'] < c_prev1['low']:
            signal, sub_pattern, ref_bar = "BUY", "S20.38", c_curr

    # [S20.39] Cancel Plan on 2L
    if not signal and sub_cfg.get("S20_39", True):
        if is_green(c_curr) and c_curr['low'] >= c_prev1['low'] and is_green(c_prev1):
            signal, sub_pattern, ref_bar = "BUY", "S20.39", c_curr

    # [S20.40] Body Over Wick Failure Pullback
    if not signal and sub_cfg.get("S20_40", True):
        if is_red(c_prev1) and is_green(c_curr) and c_curr['close'] <= c_prev1['high'] and c_curr['high'] > c_prev1['high']:
            signal, sub_pattern, ref_bar = "SELL", "S20.40", c_curr
        elif is_green(c_prev1) and is_red(c_curr) and c_curr['close'] >= c_prev1['low'] and c_curr['low'] < c_prev1['low']:
            signal, sub_pattern, ref_bar = "BUY", "S20.40", c_curr

    # [S20.41] Wick to Wick Scalp (Wick Fill Retest)
    if not signal and sub_cfg.get("S20_41", True):
        if is_green(c_prev1) and c_prev1['close'] > c_prev2['high'] and c_curr['low'] <= c_prev2['high'] and is_green(c_curr):
            signal, sub_pattern, ref_bar = "BUY", "S20.41", c_curr
        elif is_red(c_prev1) and c_prev1['close'] < c_prev2['low'] and c_curr['high'] >= c_prev2['low'] and is_red(c_curr):
            signal, sub_pattern, ref_bar = "SELL", "S20.41", c_curr

    # [S20.42] FVG 3-Level Follow Trend
    if not signal and sub_cfg.get("S20_42", True):
        if is_red(c_curr) and c_curr['low'] <= c_prev3['low'] and is_green(c_prev3):
            signal, sub_pattern, ref_bar = "BUY", "S20.42", c_curr

    # [S20.43] Sideways DM/SP Override
    if not signal and sub_cfg.get("S20_43", True):
        highs = [r['high'] for r in rates[-5:-1]]
        lows = [r['low'] for r in rates[-5:-1]]
        if max(highs) - min(lows) < atr * 1.5:
            if c_curr['low'] <= min(lows) and is_green(c_curr):
                signal, sub_pattern, ref_bar = "BUY", "S20.43", c_curr
            elif c_curr['high'] >= max(highs) and is_red(c_curr):
                signal, sub_pattern, ref_bar = "SELL", "S20.43", c_curr

    # [S20.44] 2H/2L Momentum Failure Target RUN
    if not signal and sub_cfg.get("S20_44", True):
        if c_curr['low'] >= c_prev3['low'] and c_curr['high'] <= c_prev1['high'] and is_green(c_curr):
            signal, sub_pattern, ref_bar = "BUY", "S20.44", c_curr

    # [S20.45] Solid Candle Trap (Extreme Tops/Bottoms)
    if not signal and sub_cfg.get("S20_45", True):
        if is_green(c_curr) and wick_top(c_curr) == 0 and c_curr['high'] >= max(r['high'] for r in rates[-10:]):
            signal, sub_pattern, ref_bar = "SELL", "S20.45", c_curr
        elif is_red(c_curr) and wick_bot(c_curr) == 0 and c_curr['low'] <= min(r['low'] for r in rates[-10:]) and wick_top(c_curr) > 0:
            signal, sub_pattern, ref_bar = "BUY", "S20.45", c_curr

    # [S20.46] Before Reversal Behavior Filter
    if not signal and sub_cfg.get("S20_46", True):
        if is_red(c_prev1) and body_size(c_prev1) > atr and is_green(c_curr) and c_curr['close'] > c_prev1['high']:
            signal, sub_pattern, ref_bar = "BUY", "S20.46", c_curr

    # [S20.47] Short-Term Defect Retrace (50% body limit)
    if not signal and sub_cfg.get("S20_47", True):
        if is_red(c_prev1) and wick_bot(c_prev1) > body_size(c_prev1) and is_green(c_curr) and c_curr['low'] <= (c_prev1['open'] + c_prev1['close']) / 2:
            signal, sub_pattern, ref_bar = "BUY", "S20.47", c_curr

    # [S20.48] 100% Strong OB Limit
    if not signal and sub_cfg.get("S20_48", True):
        if is_red(c_prev2) and is_green(c_prev1) and is_green(c_curr) and c_curr['low'] <= (c_prev2['open'] + c_prev2['close']) / 2:
            signal, sub_pattern, ref_bar = "BUY", "S20.48", c_curr

    # [S20.49] Long-Term Defect Magnetic Pull
    if not signal and sub_cfg.get("S20_49", True) and len(rates) >= 10:
        c_prev5 = rates[-6]
        if is_red(c_prev5) and wick_bot(c_prev5) > body_size(c_prev5) and is_red(c_curr) and c_curr['low'] <= c_prev5['low']:
            signal, sub_pattern, ref_bar = "SELL", "S20.49", c_curr

    if not signal:
        return res
        
    return {
        "signal": signal,
        "entry": round(ref_bar['close'], 2),
        "sl": round(ref_bar['low'] - atr, 2) if signal == "BUY" else round(ref_bar['high'] + atr, 2),
        "tp": round(ref_bar['close'] + (atr * 2), 2) if signal == "BUY" else round(ref_bar['close'] - (atr * 2), 2),
        "reason": f"S20 - {sub_pattern}",
        "pattern": sub_pattern,
        "sid": 20
    }
