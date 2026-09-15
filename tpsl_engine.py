import config

def get_fuel_multiplier(current_tf, target_tf):
    tf_minutes = {
        "M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440,
        "H12": 720, "W1": 10080, "MN1": 43200
    }
    cur_m = tf_minutes.get(current_tf, 60)
    tgt_m = tf_minutes.get(target_tf, 1440)
    if cur_m >= tgt_m:
        return 1.0
    return (tgt_m / cur_m) ** 0.5

def calculate_tpsl_s20_13_23(signal, current_bar, recent_3, tf, target_tf_buy="H12", target_tf_sell="D1", active_mode=2.6):
    """
    S20.13.23 / S20.13.24 TPSL Mode:
    SL: Sweep Bottom/Top + Buffer
    TP: Sweep Bottom/Top +/- (ATR * Active_Mode * FuelMultiplier)
    """
    if signal == "BUY":
        sweep_bottom = min(recent_3['low'].min(), current_bar['low'])
        sl = round(sweep_bottom - config.SL_BUFFER(current_bar['atr']), 2)
        fuel_multiplier = get_fuel_multiplier(tf, target_tf_buy)
        fuel = current_bar['atr'] * active_mode * fuel_multiplier
        tp = round(sweep_bottom + fuel, 2)
        return {"sl": sl, "tp": tp}
        
    elif signal == "SELL":
        sweep_top = max(recent_3['high'].max(), current_bar['high'])
        sl = round(sweep_top + config.SL_BUFFER(current_bar['atr']), 2)
        fuel_multiplier = get_fuel_multiplier(tf, target_tf_sell)
        fuel = current_bar['atr'] * active_mode * fuel_multiplier
        tp = round(sweep_top - fuel, 2)
        return {"sl": sl, "tp": tp}
        
    return {"sl": 0, "tp": 0}

def calculate_tpsl_s20_14_23(signal, entry_price, current_bar, df, idx):
    """
    S20.14.23 TPSL Mode:
    SL: Entry +/- (ATR * 1.5)
    TP: Find Respect High/Low from past 150 bars, fallback to ATR * 2
    """
    if signal == "BUY":
        sl = round(entry_price - (current_bar['atr'] * 1.5), 2)
        tp = round(entry_price + (current_bar['atr'] * 2), 2)
        idx_start = max(0, idx - 150)
        recent_df = df.iloc[idx_start:idx].copy()
        if len(recent_df) >= 5:
            recent_df['high_roll'] = recent_df['high'].rolling(3, center=True).max()
            highs = recent_df[recent_df['high'] == recent_df['high_roll']]
            respect_highs = []
            for h_idx in highs.index:
                loc = recent_df.index.get_loc(h_idx)
                if loc > 0:
                    h2 = recent_df.iloc[loc]
                    prev_highs = recent_df.iloc[:loc]
                    prev_highs_swing = prev_highs[prev_highs['high'] == prev_highs.get('high_roll', prev_highs['high'])]
                    if not prev_highs_swing.empty:
                        h1_pk = prev_highs_swing.iloc[-1]
                        if h2['high'] < h1_pk['high']:
                            loc1 = recent_df.index.get_loc(h1_pk.name)
                            if loc1 > 0 and h1_pk['close'] < h1_pk['open'] and h1_pk['high'] > recent_df.iloc[loc1 - 1]['high']:
                                respect_highs.append(h2['high'])
            valid_tps = [h for h in respect_highs if h > entry_price + current_bar['atr']]
            if valid_tps: 
                tp = round(valid_tps[-1], 2)
            elif recent_df['high'].max() > entry_price + current_bar['atr']: 
                tp = round(recent_df['high'].max(), 2)
        return {"sl": sl, "tp": tp}
        
    elif signal == "SELL":
        sl = round(entry_price + (current_bar['atr'] * 1.5), 2)
        tp = round(entry_price - (current_bar['atr'] * 2), 2)
        idx_start = max(0, idx - 150)
        recent_df = df.iloc[idx_start:idx].copy()
        if len(recent_df) >= 5:
            recent_df['low_roll'] = recent_df['low'].rolling(3, center=True).min()
            lows = recent_df[recent_df['low'] == recent_df['low_roll']]
            respect_lows = []
            for l_idx in lows.index:
                loc = recent_df.index.get_loc(l_idx)
                if loc > 0:
                    l2 = recent_df.iloc[loc]
                    prev_lows = recent_df.iloc[:loc]
                    prev_lows_swing = prev_lows[prev_lows['low'] == prev_lows.get('low_roll', prev_lows['low'])]
                    if not prev_lows_swing.empty:
                        l1_pk = prev_lows_swing.iloc[-1]
                        if l2['low'] > l1_pk['low']:
                            loc1 = recent_df.index.get_loc(l1_pk.name)
                            if loc1 > 0 and l1_pk['close'] > l1_pk['open'] and l1_pk['low'] < recent_df.iloc[loc1 - 1]['low']:
                                respect_lows.append(l2['low'])
            valid_tps = [l for l in respect_lows if l < entry_price - current_bar['atr']]
            if valid_tps: 
                tp = round(valid_tps[-1], 2)
            elif recent_df['low'].min() < entry_price - current_bar['atr']: 
                tp = round(recent_df['low'].min(), 2)
        return {"sl": sl, "tp": tp}
        
    return {"sl": 0, "tp": 0}

def get_tpsl(mode, signal, entry_price, current_bar, recent_3, df, idx, tf, target_tf_buy="H12", target_tf_sell="D1", active_mode=2.6):
    """
    Main Router for fetching TP/SL based on mode.
    """
    if mode == "S20.14.23":
        return calculate_tpsl_s20_14_23(signal, entry_price, current_bar, df, idx)
    else:
        # Default to S20.13.23 (Quant Fuel)
        return calculate_tpsl_s20_13_23(signal, current_bar, recent_3, tf, target_tf_buy, target_tf_sell, active_mode)
