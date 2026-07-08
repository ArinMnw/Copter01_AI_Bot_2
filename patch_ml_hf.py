import re

with open('ml_scoring.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update extract_features return value
orig_extract_end = """            z_score = z_score_series.iloc[-1]
            bb_width = bb_width_series.iloc[-1]
            adx_val = adx.iloc[-1]
            
    hour = time_bkk.hour
    is_buy = 1 if signal == "BUY" else 0
    is_sell = 1 if signal == "SELL" else 0
    
    return [hour, is_buy, is_sell, rsi_val, atr_val, ema_dist, z_score, bb_width, adx_val]"""

new_extract_end = """            z_score = z_score_series.iloc[-1]
            bb_width = bb_width_series.iloc[-1]
            adx_val = adx.iloc[-1]
            
            # Momentum Feature: (Close - Open) / ATR
            if atr_val > 0:
                price_momentum = (df['close'].iloc[-1] - df['open'].iloc[-1]) / atr_val
            else:
                price_momentum = 0.0
        else:
            price_momentum = 0.0
    else:
        price_momentum = 0.0
            
    hour = time_bkk.hour
    # Cyclical Time Encoding
    sin_hour = np.sin(2 * np.pi * hour / 24.0)
    cos_hour = np.cos(2 * np.pi * hour / 24.0)
    
    is_buy = 1 if signal == "BUY" else 0
    is_sell = 1 if signal == "SELL" else 0
    
    return [sin_hour, cos_hour, is_buy, is_sell, rsi_val, atr_val, ema_dist, z_score, bb_width, adx_val, price_momentum]"""

content = content.replace(orig_extract_end, new_extract_end)

# 2. Update train_dummy_model feature creation
orig_dummy = """    for _ in range(1000):
        hour = random.randint(0, 23)
        is_buy = random.choice([0, 1])
        is_sell = 1 - is_buy
        rsi = random.uniform(10, 90)
        atr = random.uniform(5, 60)
        ema_dist = random.uniform(-500, 500)
        z_score = random.uniform(-3.0, 3.0)
        bb_width = random.uniform(0.001, 0.02)
        adx_val = random.uniform(10, 60)
        
        X.append([hour, is_buy, is_sell, rsi, atr, ema_dist, z_score, bb_width, adx_val])"""

new_dummy = """    import numpy as np
    for _ in range(1000):
        hour = random.randint(0, 23)
        sin_hour = np.sin(2 * np.pi * hour / 24.0)
        cos_hour = np.cos(2 * np.pi * hour / 24.0)
        is_buy = random.choice([0, 1])
        is_sell = 1 - is_buy
        rsi = random.uniform(10, 90)
        atr = random.uniform(5, 60)
        ema_dist = random.uniform(-500, 500)
        z_score = random.uniform(-3.0, 3.0)
        bb_width = random.uniform(0.001, 0.02)
        adx_val = random.uniform(10, 60)
        price_mom = random.uniform(-2.0, 2.0)
        
        X.append([sin_hour, cos_hour, is_buy, is_sell, rsi, atr, ema_dist, z_score, bb_width, adx_val, price_mom])"""

content = content.replace(orig_dummy, new_dummy)

# 3. Update train_from_mt5_history loop
orig_train_loop = """        X, y = [], []
        for _, row in df_out.iterrows():
            pos_id = row['position_id']
            sid = pos_sid_map.get(pos_id, 0)
            
            # Filter for LTS only
            if sid < 80:
                continue
                
            hour = row['time'].hour
            is_buy = 1 if row['type'] == mt5.DEAL_TYPE_SELL else 0
            is_sell = 1 if row['type'] == mt5.DEAL_TYPE_BUY else 0
            success = 1 if row['profit'] > 0 else 0
            
            rsi_val, atr_val, ema_dist = 50.0, 20.0, 0.0
            z_score, bb_width, adx_val = 0.0, 1.0, 25.0
            
            if not df_rates.empty:
                idx = df_rates.index.get_indexer([row['time']], method='pad')[0]
                if idx >= 0:
                    r = df_rates.iloc[idx]
                    rsi_val = float(r.get('rsi', 50.0))
                    atr_val = float(r.get('atr', 20.0))
                    ema_dist = float(r.get('close', 0.0) - r.get('ema50', 0.0))
                    z_score = float(r.get('z_score', 0.0))
                    bb_width = float(r.get('bb_width', 1.0))
                    adx_val = float(r.get('adx', 25.0))
            
            X.append([hour, is_buy, is_sell, rsi_val, atr_val, ema_dist, z_score, bb_width, adx_val])
            y.append(success)"""

new_train_loop = """        X, y = [], []
        for _, row in df_out.iterrows():
            pos_id = row['position_id']
            sid = pos_sid_map.get(pos_id, 0)
            
            # Filter for LTS only
            if sid < 80:
                continue
                
            hour = row['time'].hour
            sin_hour = np.sin(2 * np.pi * hour / 24.0)
            cos_hour = np.cos(2 * np.pi * hour / 24.0)
            
            is_buy = 1 if row['type'] == mt5.DEAL_TYPE_SELL else 0
            is_sell = 1 if row['type'] == mt5.DEAL_TYPE_BUY else 0
            success = 1 if row['profit'] > 0 else 0
            
            rsi_val, atr_val, ema_dist = 50.0, 20.0, 0.0
            z_score, bb_width, adx_val, price_mom = 0.0, 1.0, 25.0, 0.0
            
            if not df_rates.empty:
                idx = df_rates.index.get_indexer([row['time']], method='pad')[0]
                if idx >= 0:
                    r = df_rates.iloc[idx]
                    rsi_val = float(r.get('rsi', 50.0))
                    atr_val = float(r.get('atr', 20.0))
                    ema_dist = float(r.get('close', 0.0) - r.get('ema50', 0.0))
                    z_score = float(r.get('z_score', 0.0))
                    bb_width = float(r.get('bb_width', 1.0))
                    adx_val = float(r.get('adx', 25.0))
                    if atr_val > 0:
                        price_mom = float(r.get('close', 0.0) - r.get('open', 0.0)) / atr_val
            
            X.append([sin_hour, cos_hour, is_buy, is_sell, rsi_val, atr_val, ema_dist, z_score, bb_width, adx_val, price_mom])
            y.append(success)"""

content = content.replace(orig_train_loop, new_train_loop)

with open('ml_scoring.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('ml_scoring.py updated with Hedge Fund Quant Features (Sine/Cosine + Momentum)!')
