# -*- coding: utf-8 -*-
"""strategy20_125.py
Strategy S20.125: Institutional Smart Money Flow Absorption

Core Innovations:
1. ซับแรงขาย/ซื้อระดับสถาบัน
2. Mathematically Unique Entry Logic:
   - Volume > 1.27x
   - Wick Rejection > 0.21
   - Body Momentum > 0.42
   - RSI Confluence: Buy<=57.523518720120144, Sell>=43.429508466525746
   - Requires FVG: False
   - Requires Fibo 38.2/61.8: True
   - Requires Value Area (VP): False
3. Multi-Stage Trailing (TP 12.50R)
4. Strict 0.01 Lot single position.
"""
import pandas as pd
import numpy as np

def extract_setups_s20_125(df):
    setups = []
    records = df.to_dict('records')
    min_vol = 1.27
    min_wick = 0.21
    crt_momentum = 0.42
    rsi_buy_max = 57.52
    rsi_sell_min = 43.43
    use_fvg = False
    use_fibo = True
    use_vp = False
    retest_depth = 0.142
    sl_mult = 0.10
    
    for idx in range(45, len(records)):
        cur = records[idx]
        atr = cur['atr']
        if pd.isna(atr) or atr <= 0.05 or cur['range'] < 0.45 * atr:
            continue
            
        h = cur['hour']
        if not (0 <= h <= 22):
            continue
            
        if cur['vol_ratio'] < min_vol:
            continue
            
        swept_high = False
        swept_low = False
        
        # Swings
        if cur['high'] >= cur.get('swing_high_12', np.nan): swept_high = True
        if cur['low'] <= cur.get('swing_low_12', np.nan): swept_low = True
        
        if use_fvg:
            f_bull = cur.get('fvg_bull_zone', np.nan)
            f_bear = cur.get('fvg_bear_zone', np.nan)
            if not pd.isna(f_bull) and cur['low'] <= f_bull: swept_low = True
            if not pd.isna(f_bear) and cur['high'] >= f_bear: swept_high = True
            
        if use_fibo:
            if cur['low'] <= cur.get('fibo_discount_382', np.nan): swept_low = True
            if cur['high'] >= cur.get('fibo_premium_618', np.nan): swept_high = True
            
        if use_vp:
            if cur['low'] <= cur.get('val_proxy', np.nan): swept_low = True
            if cur['high'] >= cur.get('vah_proxy', np.nan): swept_high = True
            
        # Rejection & Momentum Conditions
        bull_body = (cur['close'] - cur['open']) / (cur['range'] + 1e-5)
        bear_body = (cur['open'] - cur['close']) / (cur['range'] + 1e-5)
        
        is_rejection_bull = swept_low and (cur['lower_wick_pct'] >= min_wick) and (bull_body >= crt_momentum) and (cur['rsi'] <= rsi_buy_max)
        is_rejection_bear = swept_high and (cur['upper_wick_pct'] >= min_wick) and (bear_body >= crt_momentum) and (cur['rsi'] >= rsi_sell_min)
        
        if is_rejection_bull:
            entry = cur['close'] - (cur['lower_wick'] * retest_depth)
            sl = cur['low'] - (atr * sl_mult)
            setups.append({
                'time': int(cur['time']),
                'time_str': str(cur['time_dt']),
                'signal': 'BUY',
                'entry': entry,
                'sl': sl,
                'risk': entry - sl,
                'atr': atr,
                'tf': 'M5'
            })
        elif is_rejection_bear:
            entry = cur['close'] + (cur['upper_wick'] * retest_depth)
            sl = cur['high'] + (atr * sl_mult)
            setups.append({
                'time': int(cur['time']),
                'time_str': str(cur['time_dt']),
                'signal': 'SELL',
                'entry': entry,
                'sl': sl,
                'risk': sl - entry,
                'atr': atr,
                'tf': 'M5'
            })
    return setups
