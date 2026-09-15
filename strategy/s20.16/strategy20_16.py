import pandas as pd
import numpy as np
import config
from mt5_utils import now_bkk
import tpsl_engine

def evaluate_probability(base_type, target_price, base_price, atr):
    if atr <= 0: return 0
    diff = target_price - base_price
    atr_multiple = diff / atr
    score = 50
    if base_type == 'LOW':
        if 0.3 <= atr_multiple <= 1.8:
            score = round(95 - abs(atr_multiple - 1.2) * 20)
        elif 1.8 < atr_multiple <= 3.0:
            score = round(75 - (atr_multiple - 1.8) * 20)
        elif -0.5 <= atr_multiple < 0.3:
            score = round(60 - abs(atr_multiple) * 20)
        else:
            score = max(15, round(40 - abs(atr_multiple) * 10))
    else:
        drop_multiple = -atr_multiple
        if 0.2 <= drop_multiple <= 1.5:
            score = round(95 - abs(drop_multiple - 0.77) * 20)
        elif 1.5 < drop_multiple <= 2.5:
            score = round(70 - (drop_multiple - 1.5) * 20)
        elif -0.5 <= drop_multiple < 0.2:
            score = round(65 - abs(drop_multiple) * 0.2)
        else:
            score = max(15, round(35 - abs(drop_multiple) * 10))
    return min(95, max(15, score))

def yiaw_dam_combinator(L, H, ATR):
    if ATR <= 0: return None
    A_div = ATR / 2.6
    A_root = np.sqrt(ATR)
    
    components = [
        ("ATR", ATR),
        ("(ATR/2.6)", A_div),
        ("(√ATR)", A_root),
        ("((ATR/2.6)*2)", A_div * 2),
        ("((ATR/2.6)*3)", A_div * 3),
        ("((√ATR)*2.6)", A_root * 2.6)
    ]
    
    low_results = []
    high_results = []
    
    for i, c in enumerate(components):
        low_results.append({'calc': L + c[1], 'prob': evaluate_probability('LOW', L + c[1], L, ATR)})
        low_results.append({'calc': L - c[1], 'prob': evaluate_probability('LOW', L - c[1], L, ATR)})
        high_results.append({'calc': H - c[1], 'prob': evaluate_probability('HIGH', H - c[1], H, ATR)})
        high_results.append({'calc': H + c[1], 'prob': evaluate_probability('HIGH', H + c[1], H, ATR)})
        
    for i in range(len(components)):
        for j in range(i + 1, len(components)):
            c1 = components[i]
            c2 = components[j]
            low_results.append({'calc': L + c1[1] + c2[1], 'prob': evaluate_probability('LOW', L + c1[1] + c2[1], L, ATR)})
            low_results.append({'calc': L + c1[1] - c2[1], 'prob': evaluate_probability('LOW', L + c1[1] - c2[1], L, ATR)})
            low_results.append({'calc': L - c1[1] + c2[1], 'prob': evaluate_probability('LOW', L - c1[1] + c2[1], L, ATR)})
            
            high_results.append({'calc': H - c1[1] - c2[1], 'prob': evaluate_probability('HIGH', H - c1[1] - c2[1], H, ATR)})
            high_results.append({'calc': H - c1[1] + c2[1], 'prob': evaluate_probability('HIGH', H - c1[1] + c2[1], H, ATR)})
            high_results.append({'calc': H + c1[1] - c2[1], 'prob': evaluate_probability('HIGH', H + c1[1] - c2[1], H, ATR)})
            
    low_results.sort(key=lambda x: x['prob'], reverse=True)
    high_results.sort(key=lambda x: x['prob'], reverse=True)
    
    min_diff = float('inf')
    best_pair = None
    
    top_low = low_results[:10]
    top_high = high_results[:10]
    
    for l_item in top_low:
        for h_item in top_high:
            diff = abs(l_item['calc'] - h_item['calc'])
            if diff < min_diff:
                min_diff = diff
                best_pair = {
                    'avgPrice': (l_item['calc'] + h_item['calc']) / 2,
                    'diff': diff,
                    'combinedProb': round((l_item['prob'] + h_item['prob']) / 2)
                }
                
    if best_pair is None:
        return None
        
    base_price = best_pair['avgPrice']
    buy_price = base_price - A_root
    sell_price = base_price + A_root
    
    return {
        'base': base_price,
        'buy_zone': buy_price,
        'sell_zone': sell_price,
        'root_atr': A_root,
        'prob': best_pair['combinedProb']
    }

def compute_indicators_df(rates):
    df = pd.DataFrame(rates)
    df['time_dt'] = pd.to_datetime(df['time'], unit='s')
    df['hour'] = df['time_dt'].dt.hour
    
    # Calculate ATR
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()
    df['atr_pct'] = (df['atr'] / df['close']) * 100.0
    
    # Candle Anatomy
    df['range'] = df['high'] - df['low']
    df['body'] = np.abs(df['close'] - df['open'])
    df['body_pct'] = df['body'] / (df['range'] + 0.0001)
    
    df['upper_wick'] = df['high'] - np.maximum(df['open'], df['close'])
    df['lower_wick'] = np.minimum(df['open'], df['close']) - df['low']
    df['upper_wick_pct'] = df['upper_wick'] / (df['range'] + 0.0001)
    df['lower_wick_pct'] = df['lower_wick'] / (df['range'] + 0.0001)

    df['vol_ma20'] = df['tick_volume'].rolling(20).mean()
    df['vol_ratio'] = df['tick_volume'] / (df['vol_ma20'] + 1.0)
    
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['dist_ema50'] = df['close'] - df['ema_50']
    df['dist_ema200'] = df['close'] - df['ema_200']
    
    delta = df['close'].diff()
    gain14 = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss14 = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs14 = gain14 / loss14
    df['rsi'] = 100 - (100 / (1 + rs14))
    
    gain7 = (delta.where(delta > 0, 0)).rolling(window=7).mean()
    loss7 = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
    rs7 = gain7 / loss7
    df['rsi_7'] = 100 - (100 / (1 + rs7))

    sma_20 = df['close'].rolling(20).mean()
    std_20 = df['close'].rolling(20).std()
    df['z_score'] = (df['close'] - sma_20) / std_20
    
    plus_dm = df['high'].diff()
    minus_dm = df['low'].shift() - df['low']
    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
    tr14 = tr.rolling(14).sum()
    plus_di14 = 100 * (pd.Series(plus_dm).rolling(14).sum() / tr14)
    minus_di14 = 100 * (pd.Series(minus_dm).rolling(14).sum() / tr14)
    dx = 100 * (np.abs(plus_di14 - minus_di14) / (plus_di14 + minus_di14))
    df['adx'] = dx.rolling(14).mean()
    df['di_diff'] = plus_di14 - minus_di14
    return df

def evaluate_bar(df, idx, tf="H1"):
    if idx < 20 or idx >= len(df):
        return {"signal": "WAIT", "reason": "Not enough data"}

    current_bar = df.iloc[idx]
    prev_bar = df.iloc[idx - 1]
    
    if pd.isna(current_bar['atr']) or pd.isna(current_bar['rsi']) or pd.isna(current_bar['ema_200']):
        return {"signal": "WAIT", "reason": "Indicators not ready"}

    lookback_bars = df.iloc[max(0, idx - 14) : max(0, idx - 3)]
    if len(lookback_bars) == 0:
        return {"signal": "WAIT", "reason": "Not enough data"}
        
    local_low = lookback_bars['low'].min()
    local_high = lookback_bars['high'].max()
    
    active_mode = getattr(config, "S20_16_ACTIVE_MODE", 2.6)
    target_tf_buy = getattr(config, "S20_16_TARGET_TF_BUY", "H12")
    target_tf_sell = getattr(config, "S20_16_TARGET_TF_SELL", "D1")
    tpsl_mode = getattr(config, "S20_16_TPSL_MODE", "DYNAMIC")
    if tpsl_mode == "DYNAMIC":
        tpsl_mode = "S20.14.23" if tf in ("M1", "M5") else "S20.13.23"
    
    current_time = current_bar['time_dt']
    hour = current_time.hour
    is_ny_pre_open = (hour == 12 or hour == 13)
    is_sydney_open = (hour == 23 or hour == 0)
    is_london_open = (hour == 8)
    is_london_fake = (hour == 9)
    
    cur_range = current_bar['high'] - current_bar['low']
    is_strong_range = cur_range >= (0.8 * current_bar['atr'])

    recent_3 = df.iloc[max(0, idx - 3) : idx]
    
    # Calculate YiawDam Zones based on local swing
    yd = yiaw_dam_combinator(local_low, local_high, current_bar['atr'])

    # -------------------------------------------------------------
    # BUY PA CONFIRMATION (CHoCH / Engulfing)
    # -------------------------------------------------------------
    sweep_buy = recent_3['low'].min() < local_low
    engulf_buy = current_bar['close'] > prev_bar['high']
    instant_sweep_buy = current_bar['low'] < local_low and current_bar['close'] > prev_bar['high']
    
    if (sweep_buy and engulf_buy) or instant_sweep_buy:
        if not is_strong_range:
            return {"signal": "WAIT", "reason": "Engulfing Range < 0.8 ATR"}
        if is_ny_pre_open or is_sydney_open or is_london_open or is_london_fake:
            return {"signal": "WAIT", "reason": "Session Time Trap"}
            
        if current_bar['rsi'] < 35:
            return {"signal": "WAIT", "reason": f"RSI too low ({current_bar['rsi']:.1f})"}
            
        if yd is None:
            return {"signal": "WAIT", "reason": "YiawDam Calculation Failed"}
            
        entry_price = yd['buy_zone']
        
        tpsl = tpsl_engine.get_tpsl(
            mode=tpsl_mode, signal="BUY", entry_price=entry_price,
            current_bar=current_bar, recent_3=recent_3, df=df, idx=idx, tf=tf,
            target_tf_buy=target_tf_buy, target_tf_sell=target_tf_sell, active_mode=active_mode
        )
        sl, tp = tpsl["sl"], tpsl["tp"]
        
        return {
            "signal": "BUY",
            "entry": entry_price,
            "sl": sl,
            "tp": tp,
            "pattern": f"S20.16 YiawDam BUY (Prob {yd['prob']}%)",
            "order_mode": "limit",
            "reason": f"YiawDam Base {yd['base']:.2f} | TP {tp:.2f}"
        }
        
    # -------------------------------------------------------------
    # SELL PA CONFIRMATION (CHoCH / Engulfing)
    # -------------------------------------------------------------
    sweep_sell = recent_3['high'].max() > local_high
    engulf_sell = current_bar['close'] < prev_bar['low']
    instant_sweep_sell = current_bar['high'] > local_high and current_bar['close'] < prev_bar['low']
    
    if (sweep_sell and engulf_sell) or instant_sweep_sell:
        if not is_strong_range:
            return {"signal": "WAIT", "reason": "Engulfing Range < 0.8 ATR"}
        if is_ny_pre_open or is_sydney_open or is_london_open or is_london_fake:
            return {"signal": "WAIT", "reason": "Session Time Trap"}
            
        if current_bar['rsi'] > 60:
            return {"signal": "WAIT", "reason": f"RSI too high ({current_bar['rsi']:.1f})"}
            
        if yd is None:
            return {"signal": "WAIT", "reason": "YiawDam Calculation Failed"}
            
        entry_price = yd['sell_zone']
        
        tpsl = tpsl_engine.get_tpsl(
            mode=tpsl_mode, signal="SELL", entry_price=entry_price,
            current_bar=current_bar, recent_3=recent_3, df=df, idx=idx, tf=tf,
            target_tf_buy=target_tf_buy, target_tf_sell=target_tf_sell, active_mode=active_mode
        )
        sl, tp = tpsl["sl"], tpsl["tp"]
        
        return {
            "signal": "SELL",
            "entry": entry_price,
            "sl": sl,
            "tp": tp,
            "pattern": f"S20.16 YiawDam SELL (Prob {yd['prob']}%)",
            "order_mode": "limit",
            "reason": f"YiawDam Base {yd['base']:.2f} | TP {tp:.2f}"
        }

    return {"signal": "WAIT", "reason": "No Setup"}
