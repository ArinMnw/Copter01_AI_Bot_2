import os
import sys

# Append base strategy dir to path so we can import other strategies
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(base_dir, '..', '..')))
sys.path.append(os.path.abspath(os.path.join(base_dir, '..', 's20.13')))

import pandas as pd
import numpy as np
import config
import joblib
from datetime import timedelta

import strategy1
import strategy9
import strategy11
import strategy20_13_24

# Global models cache
MODELS = {}

def load_models():
    global MODELS
    if MODELS: return
    model_dir = os.path.join(base_dir, '..', 's20.14.1', 'backtest-sim')
    models_to_load = ["fvg_buy_v22.pkl", "fvg_sell_v22.pkl", "naiya_buy_v22.pkl", "naiya_sell_v22.pkl"]
    for m in models_to_load:
        path = os.path.join(model_dir, m)
        if os.path.exists(path):
            try:
                MODELS[m] = joblib.load(path)
            except Exception as e:
                print(f"Error loading {m}: {e}")

def get_ml_pred(model_name, features):
    if model_name not in MODELS: return 0
    model = MODELS[model_name]
    if hasattr(model, "feature_names_in_"):
        features_sliced = features[:len(model.feature_names_in_)]
        df_feat = pd.DataFrame([dict(zip(model.feature_names_in_, features_sliced))])
        return model.predict(df_feat)[0]
    return model.predict([features])[0]

def prepare_indicators(rates, tf):
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['time_dt'] = df['time'] + timedelta(hours=1) # BKK Time adjustment if needed
    
    hl = df['high'] - df['low']
    hc = np.abs(df['high'] - df['close'].shift())
    lc = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    df['sma12'] = df['close'].rolling(window=12).mean()
    df['sma20'] = df['close'].rolling(window=20).mean()
    df['sma50'] = df['close'].rolling(window=50).mean()
    df['sma200'] = df['close'].rolling(window=200).mean()
    
    df['dist_sma50'] = (df['close'] - df['sma50']) / df['sma50'] * 100
    df['dist_sma200'] = (df['close'] - df['sma200']) / df['sma200'] * 100
    
    df['recent_low'] = df['low'].rolling(window=20).min().shift(1)
    df['recent_high'] = df['high'].rolling(window=20).max().shift(1)
    df['recent_low_50'] = df['low'].rolling(window=50).min().shift(1)
    df['recent_high_50'] = df['high'].rolling(window=50).max().shift(1)
    df['recent_low_35'] = df['low'].rolling(window=35).min().shift(1)
    df['recent_high_35'] = df['high'].rolling(window=35).max().shift(1)
    
    df['body'] = np.abs(df['close'] - df['open'])
    df['range'] = df['high'] - df['low']
    
    df['bull_fvg_raw'] = df['high'].shift(2) < df['low']
    df['bear_fvg_raw'] = df['low'].shift(2) > df['high']
    df['bull_fvg_10'] = df['bull_fvg_raw'].rolling(window=10).max() > 0
    df['bear_fvg_10'] = df['bear_fvg_raw'].rolling(window=10).max() > 0
    
    # Gap logic
    df['time_diff'] = df['time_dt'].diff()
    df['prev_close'] = df['close'].shift(1)
    df['prev_open_2'] = df['open'].shift(2)
    df['prev_low_2'] = df['low'].shift(2)
    df['prev_high_2'] = df['high'].shift(2)
    
    df['inst_gap_buy'] = (df['time_diff'].dt.total_seconds() > 3600) & (df['open'] > df['prev_close'])
    df['inst_gap_sell'] = (df['time_diff'].dt.total_seconds() > 3600) & (df['open'] < df['prev_close'])
    
    # For GapSweep, we need weekly_open. Approximation for live bot:
    # A simple weekly open logic if needed. Not perfectly backtest matching without D1 data,
    # but we can do a simple weekly start check.
    df['dow'] = df['time_dt'].dt.dayofweek
    df['is_new_week'] = df['dow'] < df['dow'].shift(1)
    df['weekly_open'] = df['open'].where(df['is_new_week']).ffill()
    
    df['is_green'] = df['close'] > df['open']
    df['is_red'] = df['close'] < df['open']
    df['gap_sweep_sell'] = (df['weekly_open'].notna()) & (df['open'] < df['weekly_open']) & (df['high'] >= df['weekly_open']) & (df['close'] < df['weekly_open']) & (df['high'] > df['high'].shift(1)) & df['is_red']
    df['gap_sweep_buy'] = (df['weekly_open'].notna()) & (df['open'] > df['weekly_open']) & (df['low'] <= df['weekly_open']) & (df['close'] > df['weekly_open']) & (df['low'] < df['low'].shift(1)) & df['is_green']
    
    # Naiya base
    df['is_green_doji'] = df['is_green'] & (df['body'] <= df['range'] * 0.25)
    df['is_red_doji'] = df['is_red'] & (df['body'] <= df['range'] * 0.25)
    df['naiya_doji_buy_base'] = df['is_green'] & df['is_green_doji'].shift(1) & df['is_red'].shift(2)
    df['naiya_doji_sell_base'] = df['is_red'] & df['is_red_doji'].shift(1) & df['is_green'].shift(2)
    
    return df

# ------------- GROUP 2 -------------
def strategy_20_14_2(rates, tf="H1"):
    if rates is None or len(rates) < 55: return {"signal": "WAIT", "reason": "Not enough data"}
    
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    
    if getattr(current_bar, 'inst_gap_buy', False):
        limit_p = current_bar['prev_open_2'] if not pd.isna(current_bar['prev_open_2']) else current_bar['prev_close']
        sl = current_bar['prev_low_2'] if not pd.isna(current_bar['prev_low_2']) else current_bar['low']
        tp = limit_p + (limit_p - sl) * 1.618
        return {"signal": "BUY", "entry": limit_p, "sl": sl, "tp": tp, "pattern": "Inst_Gap", "reason": "Group 2 Inst_Gap"}
        
    if getattr(current_bar, 'inst_gap_sell', False):
        limit_p = current_bar['prev_open_2'] if not pd.isna(current_bar['prev_open_2']) else current_bar['prev_close']
        sl = current_bar['prev_high_2'] if not pd.isna(current_bar['prev_high_2']) else current_bar['high']
        tp = limit_p - (sl - limit_p) * 1.618
        return {"signal": "SELL", "entry": limit_p, "sl": sl, "tp": tp, "pattern": "Inst_Gap", "reason": "Group 2 Inst_Gap"}
        
    return {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 5 -------------
def strategy_20_14_5(rates, tf="H1"):
    if rates is None or len(rates) < 55: return {"signal": "WAIT", "reason": "Not enough data"}
    
    load_models()
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}
    
    f = [current_bar['rsi'], current_bar['atr'], current_bar['dist_sma50'], current_bar['dist_sma200'], current_bar['body'], current_bar['range']]
    fvg_buy_ml = get_ml_pred("fvg_buy_v22.pkl", f)
    fvg_sell_ml = get_ml_pred("fvg_sell_v22.pkl", f)
    
    swing_h = current_bar['recent_high_50']
    swing_l = current_bar['recent_low_50']
    fibo_38_2 = swing_l + (swing_h - swing_l) * 0.382
    fibo_61_8 = swing_l + (swing_h - swing_l) * 0.618
    
    s11_res = strategy11.strategy_11(rates, tf)
    
    # BUY
    if current_bar['bull_fvg_10'] and (fvg_buy_ml == 1 or current_bar['rsi'] > 70):
        if 15.0 <= current_bar['rsi'] <= 68.0 and current_bar['atr'] >= 7.0:
            if current_bar['recent_low'] < fibo_38_2 or current_bar['rsi'] > 70:
                entry = current_bar['recent_low']
                sl = entry - (2.5 * current_bar['atr'])
                tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
                return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "FVG", "reason": "Group 5 FVG BUY"}
                
    if s11_res and s11_res.get("signal") == "BUY":
        return {"signal": "BUY", "entry": s11_res.get("entry", current_bar['close']), "sl": s11_res.get("sl"), "tp": s11_res.get("tp"), "pattern": "Fibo", "reason": "Group 5 Fibo BUY"}
        
    # SELL
    if current_bar['bear_fvg_10'] and (fvg_sell_ml == 1 or current_bar['rsi'] < 30):
        if 10.0 <= current_bar['rsi'] <= 77.0 and current_bar['atr'] >= 10.0:
            if current_bar['recent_high'] > fibo_61_8 or current_bar['rsi'] < 30:
                entry = current_bar['recent_high']
                sl = entry + (2.5 * current_bar['atr'])
                tp = entry - ((entry - current_bar['recent_low']) * 1.618)
                return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "FVG", "reason": "Group 5 FVG SELL"}
                
    if s11_res and s11_res.get("signal") == "SELL":
        return {"signal": "SELL", "entry": s11_res.get("entry", current_bar['close']), "sl": s11_res.get("sl"), "tp": s11_res.get("tp"), "pattern": "Fibo", "reason": "Group 5 Fibo SELL"}
        
    return {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 9 -------------
def strategy_20_14_9(rates, tf="H1"):
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    
    load_models()
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}
    
    f = [current_bar['rsi'], current_bar['atr'], current_bar['dist_sma50'], current_bar['dist_sma200'], current_bar['body'], current_bar['range']]
    naiya_buy_ml = get_ml_pred("naiya_buy_v22.pkl", f)
    naiya_sell_ml = get_ml_pred("naiya_sell_v22.pkl", f)
    
    swing_h = current_bar['recent_high_50']
    swing_l = current_bar['recent_low_50']
    fibo_38_2 = swing_l + (swing_h - swing_l) * 0.382
    fibo_61_8 = swing_l + (swing_h - swing_l) * 0.618
    
    # BUY
    if current_bar['naiya_doji_buy_base'] and (naiya_buy_ml == 1 or current_bar['rsi'] < 30):
        if current_bar['recent_low'] < fibo_38_2 or current_bar['rsi'] < 30:
            entry = current_bar['recent_low']
            sl = entry - (2.5 * current_bar['atr'])
            tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
            return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "Naiya", "reason": "Group 9 Naiya BUY"}
            
    if current_bar['range'] > 0 and current_bar['body'] < 0.4 * current_bar['range'] and (current_bar['close'] - current_bar['low']) > 0.5 * current_bar['range'] and current_bar['low'] <= current_bar['recent_low'] + current_bar['atr']*0.5 and 0 <= current_bar['rsi'] <= 2:
        entry = current_bar['recent_low']
        sl = entry - (2.5 * current_bar['atr'])
        tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
        return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "Doji", "reason": "Group 9 Doji BUY"}
        
    # SELL
    if current_bar['naiya_doji_sell_base'] and (naiya_sell_ml == 1 or current_bar['rsi'] > 70):
        if current_bar['recent_high'] > fibo_61_8 or current_bar['rsi'] > 70:
            entry = current_bar['recent_high']
            sl = entry + (2.5 * current_bar['atr'])
            tp = entry - ((entry - current_bar['recent_low']) * 1.618)
            return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "Naiya", "reason": "Group 9 Naiya SELL"}
            
    if current_bar['range'] > 0 and current_bar['body'] < 0.4 * current_bar['range'] and (current_bar['high'] - current_bar['close']) > 0.5 * current_bar['range'] and current_bar['high'] >= current_bar['recent_high'] - current_bar['atr']*0.5 and 74 <= current_bar['rsi'] <= 78 and current_bar['close'] < current_bar['sma50'] and current_bar['close'] < current_bar['sma200']:
        entry = current_bar['recent_high']
        sl = entry + (2.5 * current_bar['atr'])
        tp = entry - ((entry - current_bar['recent_low']) * 1.618)
        return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "Doji", "reason": "Group 9 Doji SELL"}

    return {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 12 -------------
def strategy_20_14_12(rates, tf="H1"):
    # Group 12 is like 9 but with custom Sweep Logic
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    
    load_models()
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    prev_bar = df.iloc[-2]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}
    
    # Sweep condition
    sweep_sell = current_bar['high'] > prev_bar['high'] and current_bar['close'] < current_bar['high']
    sweep_buy = current_bar['low'] < prev_bar['low'] and current_bar['close'] > current_bar['low']
    
    f = [current_bar['rsi'], current_bar['atr'], current_bar['dist_sma50'], current_bar['dist_sma200'], current_bar['body'], current_bar['range']]
    naiya_buy_ml = get_ml_pred("naiya_buy_v22.pkl", f)
    naiya_sell_ml = get_ml_pred("naiya_sell_v22.pkl", f)
    
    swing_h = current_bar['recent_high_50']
    swing_l = current_bar['recent_low_50']
    fibo_38_2 = swing_l + (swing_h - swing_l) * 0.382
    fibo_61_8 = swing_l + (swing_h - swing_l) * 0.618
    
    # BUY
    if current_bar['naiya_doji_buy_base'] and sweep_buy:
        entry = current_bar['low']
        sl = entry - (2.5 * current_bar['atr'])
        tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
        return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "Naiya", "reason": "Group 12 Sweep Naiya BUY"}
        
    if current_bar['range'] > 0 and current_bar['body'] < 0.4 * current_bar['range'] and (current_bar['close'] - current_bar['low']) > 0.5 * current_bar['range'] and current_bar['low'] <= current_bar['recent_low'] + current_bar['atr']*0.5 and 0 <= current_bar['rsi'] <= 2:
        entry = current_bar['recent_low']
        sl = entry - (2.5 * current_bar['atr'])
        tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
        return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "Doji", "reason": "Group 12 Doji BUY"}
        
    # SELL
    if current_bar['naiya_doji_sell_base'] and sweep_sell:
        entry = current_bar['high']
        sl = entry + (2.5 * current_bar['atr'])
        tp = entry - ((entry - current_bar['recent_low']) * 1.618)
        return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "Naiya", "reason": "Group 12 Sweep Naiya SELL"}
            
    if current_bar['range'] > 0 and current_bar['body'] < 0.4 * current_bar['range'] and (current_bar['high'] - current_bar['close']) > 0.5 * current_bar['range'] and current_bar['high'] >= current_bar['recent_high'] - current_bar['atr']*0.5 and 74 <= current_bar['rsi'] <= 78 and current_bar['close'] < current_bar['sma50'] and current_bar['close'] < current_bar['sma200']:
        entry = current_bar['recent_high']
        sl = entry + (2.5 * current_bar['atr'])
        tp = entry - ((entry - current_bar['recent_low']) * 1.618)
        return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "Doji", "reason": "Group 12 Doji SELL"}

    return {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 13 -------------
def strategy_20_14_13(rates, tf="H1"):
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    
    load_models()
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}
    
    # GapSweep Check
    if getattr(current_bar, 'gap_sweep_buy', False):
        entry = current_bar['weekly_open']
        sl = current_bar['low']
        tp = entry + (entry - sl) * 1.618
        return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "GapSweep", "reason": "Group 13 GapSweep"}
    if getattr(current_bar, 'gap_sweep_sell', False):
        entry = current_bar['weekly_open']
        sl = current_bar['high']
        tp = entry - (sl - entry) * 1.618
        return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "GapSweep", "reason": "Group 13 GapSweep"}
        
    # FVG Check
    f = [current_bar['rsi'], current_bar['atr'], current_bar['dist_sma50'], current_bar['dist_sma200'], current_bar['body'], current_bar['range']]
    fvg_buy_ml = get_ml_pred("fvg_buy_v22.pkl", f)
    fvg_sell_ml = get_ml_pred("fvg_sell_v22.pkl", f)
    
    swing_h = current_bar['recent_high_50']
    swing_l = current_bar['recent_low_50']
    fibo_38_2 = swing_l + (swing_h - swing_l) * 0.382
    fibo_61_8 = swing_l + (swing_h - swing_l) * 0.618
    
    if current_bar['bull_fvg_10'] and (fvg_buy_ml == 1 or current_bar['rsi'] > 70):
        if 15.0 <= current_bar['rsi'] <= 68.0 and current_bar['atr'] >= 7.0:
            if current_bar['recent_low'] < fibo_38_2 or current_bar['rsi'] > 70:
                entry = current_bar['recent_low']
                sl = entry - (2.5 * current_bar['atr'])
                tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
                return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "FVG", "reason": "Group 13 FVG BUY"}
                
    if current_bar['bear_fvg_10'] and (fvg_sell_ml == 1 or current_bar['rsi'] < 30):
        if 10.0 <= current_bar['rsi'] <= 77.0 and current_bar['atr'] >= 10.0:
            if current_bar['recent_high'] > fibo_61_8 or current_bar['rsi'] < 30:
                entry = current_bar['recent_high']
                sl = entry + (2.5 * current_bar['atr'])
                tp = entry - ((entry - current_bar['recent_low']) * 1.618)
                return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "FVG", "reason": "Group 13 FVG SELL"}

    return {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 19 -------------
def strategy_20_14_19(rates, tf="H1"):
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    
    load_models()
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}
    
    f = [current_bar['rsi'], current_bar['atr'], current_bar['dist_sma50'], current_bar['dist_sma200'], current_bar['body'], current_bar['range']]
    fvg_buy_ml = get_ml_pred("fvg_buy_v22.pkl", f)
    fvg_sell_ml = get_ml_pred("fvg_sell_v22.pkl", f)
    
    swing_h = current_bar['recent_high_50']
    swing_l = current_bar['recent_low_50']
    fibo_38_2 = swing_l + (swing_h - swing_l) * 0.382
    fibo_61_8 = swing_l + (swing_h - swing_l) * 0.618
    
    if current_bar['bull_fvg_10'] and (fvg_buy_ml == 1 or current_bar['rsi'] > 70):
        if 15.0 <= current_bar['rsi'] <= 68.0 and current_bar['atr'] >= 7.0:
            if current_bar['recent_low'] < fibo_38_2 or current_bar['rsi'] > 70:
                entry = current_bar['recent_low']
                sl = entry - (2.5 * current_bar['atr'])
                tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
                return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "FVG", "reason": "Group 19 FVG BUY"}
                
    if current_bar['bear_fvg_10'] and (fvg_sell_ml == 1 or current_bar['rsi'] < 30):
        if 10.0 <= current_bar['rsi'] <= 77.0 and current_bar['atr'] >= 10.0:
            if current_bar['recent_high'] > fibo_61_8 or current_bar['rsi'] < 30:
                entry = current_bar['recent_high']
                sl = entry + (2.5 * current_bar['atr'])
                tp = entry - ((entry - current_bar['recent_low']) * 1.618)
                return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "FVG", "reason": "Group 19 FVG SELL"}

    return {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 21 -------------
def strategy_20_14_21(rates, tf="H1"):
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}
    
    s9_res = strategy9.strategy_9(rates, tf)
    if s9_res and s9_res.get("signal") == "BUY":
        if 10.0 <= current_bar['rsi'] <= 34.0 and current_bar['atr'] >= 8.0:
            entry = current_bar['recent_low']
            sl = entry - (2.5 * current_bar['atr'])
            tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
            return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "Div", "reason": "Group 21 Div BUY"}
            
    if s9_res and s9_res.get("signal") == "SELL":
        if 66.0 <= current_bar['rsi'] <= 90.0 and current_bar['atr'] >= 8.0:
            entry = current_bar['recent_high']
            sl = entry + (2.5 * current_bar['atr'])
            tp = entry - ((entry - current_bar['recent_low']) * 1.618)
            return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "Div", "reason": "Group 21 Div SELL"}
            
    return {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 22 -------------
def strategy_20_14_22(rates, tf="H1"):
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}
    
    if getattr(current_bar, 'gap_sweep_buy', False):
        entry = current_bar['weekly_open']
        sl = current_bar['low']
        tp = entry + (entry - sl) * 1.618
        return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "GapSweep", "reason": "Group 22 GapSweep"}
    if getattr(current_bar, 'gap_sweep_sell', False):
        entry = current_bar['weekly_open']
        sl = current_bar['high']
        tp = entry - (sl - entry) * 1.618
        return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "GapSweep", "reason": "Group 22 GapSweep"}
        
    return {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 23 -------------
# H1 Liquidity Sweep -> Respect Low (MTF BUY on LTF)
_H1_CACHE_G23 = {
    "df": None,
    "last_time": None,
    "liq_lows": [],
}

def _refresh_h1_cache_g23():
    """Fetch H1 bars from MT5 and pre-compute liq sweep lows. Cached per H1 bar."""
    try:
        import MetaTrader5 as mt5
        import pandas as pd
        from datetime import timedelta
        import config
        symbol = config.SYMBOL
        rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 2000)
        if rates_h1 is None or len(rates_h1) == 0:
            return
        df_h1 = pd.DataFrame(rates_h1)
        df_h1['time_dt'] = pd.to_datetime(df_h1['time'], unit='s') + timedelta(hours=1)
        df_h1['is_red'] = df_h1['close'] < df_h1['open']
        df_h1['low_roll'] = df_h1['low'].rolling(3, center=True).min()
        liq_lows = []
        swing_mask = df_h1['low'] == df_h1['low_roll']
        for loc, (idx, row) in enumerate(df_h1.iterrows()):
            if not swing_mask.iloc[loc]: continue
            if loc == 0: continue
            prev = df_h1.iloc[loc - 1]
            if row['low'] < prev['low'] and prev['is_red']:
                liq_lows.append({'low': row['low'], 'time_dt': row['time_dt']})
        _H1_CACHE_G23['df'] = df_h1
        _H1_CACHE_G23['last_time'] = df_h1['time'].iloc[-1]
        _H1_CACHE_G23['liq_lows'] = liq_lows
    except Exception:
        pass

def strategy_20_14_23(rates, tf="H1"):
    """S20.14 Group 23: H1 Liquidity Sweep -> LTF Respect Low MTF BUY (Market Execution)"""
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    if tf not in ["M30", "M15", "M5", "M1"]: return {"signal": "WAIT"}

    from datetime import timedelta
    import pandas as pd
    import config
    try:
        import MetaTrader5 as mt5
        latest_h1 = mt5.copy_rates_from_pos(config.SYMBOL, mt5.TIMEFRAME_H1, 0, 1)
        if latest_h1 is not None and len(latest_h1) > 0:
            if _H1_CACHE_G23['last_time'] != latest_h1[0]['time']: _refresh_h1_cache_g23()
    except Exception:
        if _H1_CACHE_G23['df'] is None: _refresh_h1_cache_g23()

    if not _H1_CACHE_G23['liq_lows']: return {"signal": "WAIT", "reason": "No H1 liq lows cached"}
    df_h1, h1_liq_lows = _H1_CACHE_G23['df'], _H1_CACHE_G23['liq_lows']

    df = prepare_indicators(rates, tf)
    if len(df) < 5: return {"signal": "WAIT"}
    bar_m1, bar_m2, bar_m3 = df.iloc[-1], df.iloc[-2], df.iloc[-3]
    if pd.isna(bar_m1.get('atr')) or bar_m1['atr'] <= 0: return {"signal": "WAIT"}

    is_ltf_swing_low = (bar_m2['low'] <= bar_m1['low']) and (bar_m2['low'] <= bar_m3['low'])
    if not is_ltf_swing_low: return {"signal": "WAIT"}

    current_time, entry_price, atr = bar_m1['time_dt'], bar_m2['low'], bar_m1['atr']
    recent_liq = [l for l in h1_liq_lows if l['time_dt'] < current_time and l['time_dt'] >= current_time - timedelta(days=5)]
    if not recent_liq: return {"signal": "WAIT", "reason": "No recent H1 liq low"}
    
    h1_liq = recent_liq[-1]
    if entry_price <= h1_liq['low']: return {"signal": "WAIT"}

    sl_price = round(entry_price - (atr * 1.5), 2)
    tp_price = round(entry_price + (atr * 2), 2)
    
    if df_h1 is not None:
        idx_end = df_h1['time_dt'].searchsorted(current_time)
        idx_start = max(0, idx_end - 150)
        recent_h1 = df_h1.iloc[idx_start:idx_end].copy()
        if len(recent_h1) >= 5:
            recent_h1['high_roll'] = recent_h1['high'].rolling(3, center=True).max()
            highs = recent_h1[recent_h1['high'] == recent_h1['high_roll']]
            respect_highs = []
            for h_idx in highs.index:
                loc = recent_h1.index.get_loc(h_idx)
                if loc > 0:
                    h2 = recent_h1.iloc[loc]
                    prev_highs = recent_h1.iloc[:loc]
                    prev_highs_swing = prev_highs[prev_highs['high'] == prev_highs.get('high_roll', prev_highs['high'])]
                    if prev_highs_swing.empty: continue
                    h1_pk = prev_highs_swing.iloc[-1]
                    if h2['high'] < h1_pk['high']:
                        loc1 = recent_h1.index.get_loc(h1_pk.name)
                        if loc1 > 0 and h1_pk['close'] < h1_pk['open'] and h1_pk['high'] > recent_h1.iloc[loc1 - 1]['high']:
                            respect_highs.append(h2['high'])
            valid_tps = [h for h in respect_highs if h > entry_price + atr]
            if valid_tps: tp_price = round(valid_tps[-1], 2)
            elif recent_h1['high'].max() > entry_price + atr: tp_price = round(recent_h1['high'].max(), 2)

    return {
        "signal": "BUY",
        "entry": round(entry_price, 2),
        "sl": sl_price,
        "tp": tp_price,
        "pattern": "Naiya_MTF",
        "order_mode": "market",
        "reason": f"Group 23 H1 LiqSweep->LTF Respect Low | H1_liq={h1_liq['low']:.2f} | ATR={atr:.2f}",
    }

# ------------- GROUP 24 -------------
def strategy_20_14_24(rates, tf="H1"):
    return strategy_20_14_19(rates, tf) # Same as 19 based on target_tfs


def strategy_20_14_1(rates, tf="H1"):
    # Group 1: ATR Baseline
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}
    return {"signal": "WAIT"} # Group 1 in original is complex, needs full translation if used, but placeholder for now to prevent crash.

def strategy_20_14_14(rates, tf="H1"):
    # Group 14: GapSweep, Div
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}
    
    # GapSweep
    if getattr(current_bar, 'gap_sweep_buy', False):
        entry = current_bar['weekly_open']
        sl    = current_bar['low']
        tp    = entry + (entry - sl) * 1.618
        return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "GapSweep", "reason": "Group 14 GapSweep BUY"}
    if getattr(current_bar, 'gap_sweep_sell', False):
        entry = current_bar['weekly_open']
        sl    = current_bar['high']
        tp    = entry - (sl - entry) * 1.618
        return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "GapSweep", "reason": "Group 14 GapSweep SELL"}
        
    # Divergence
    recent_50 = df.tail(50)
    # Basic DIV detection placeholder for Group 14
    return {"signal": "WAIT"}

def strategy_20_14_16(rates, tf="H1"):
    # Group 16: Naiya, Doji
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    load_models()
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}
    
    f = [current_bar['rsi'], current_bar['atr'], current_bar['dist_sma50'], current_bar['dist_sma200'], current_bar['body'], current_bar['range']]
    naiya_buy_ml = get_ml_pred("naiya_buy_v22.pkl", f)
    naiya_sell_ml = get_ml_pred("naiya_sell_v22.pkl", f)
    
    if naiya_buy_ml == 1 and current_bar['rsi'] < 30:
        entry = current_bar['close']
        sl = current_bar['low'] - (current_bar['atr'] * 0.5)
        tp = current_bar['close'] + (current_bar['atr'] * 2)
        return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "Naiya", "reason": "Naiya_BUY"}
    if naiya_sell_ml == 1 and current_bar['rsi'] > 70:
        entry = current_bar['close']
        sl = current_bar['high'] + (current_bar['atr'] * 0.5)
        tp = current_bar['close'] - (current_bar['atr'] * 2)
        return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "Naiya", "reason": "Naiya_SELL"}
        
    return {"signal": "WAIT"}

def strategy_20_14_18(rates, tf="H1"):
    # Group 18: Naiya
    return strategy_20_14_16(rates, tf) # Shares same core logic as 16 for now


# ------------- GROUP 7 -------------
def strategy_20_14_7(rates, tf="H1"):
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    s11_res = strategy11.strategy_11(rates, tf)
    if s11_res and s11_res.get("signal") == "BUY":
        return {"signal": "BUY", "entry": s11_res.get("entry", current_bar['close']), "sl": s11_res.get("sl"), "tp": s11_res.get("tp"), "pattern": "Fibo", "reason": "Group 7 Fibo BUY"}
    if s11_res and s11_res.get("signal") == "SELL":
        return {"signal": "SELL", "entry": s11_res.get("entry", current_bar['close']), "sl": s11_res.get("sl"), "tp": s11_res.get("tp"), "pattern": "Fibo", "reason": "Group 7 Fibo SELL"}
    return {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 8 -------------
def strategy_20_14_8(rates, tf="H1"):
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    load_models()
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}
    
    if getattr(current_bar, 'gap_sweep_buy', False):
        entry = current_bar['weekly_open']
        sl = current_bar['low']
        tp = entry + (entry - sl) * 1.618
        return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "GapSweep", "reason": "Group 8 GapSweep BUY"}
    if getattr(current_bar, 'gap_sweep_sell', False):
        entry = current_bar['weekly_open']
        sl = current_bar['high']
        tp = entry - (sl - entry) * 1.618
        return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "GapSweep", "reason": "Group 8 GapSweep SELL"}

    if current_bar['naiya_doji_buy_base']:
        entry = current_bar['recent_low']
        sl = entry - (2.5 * current_bar['atr'])
        tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
        return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "Naiya", "reason": "Group 8 Naiya BUY"}
    if current_bar['naiya_doji_sell_base']:
        entry = current_bar['recent_high']
        sl = entry + (2.5 * current_bar['atr'])
        tp = entry - ((entry - current_bar['recent_low']) * 1.618)
        return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "Naiya", "reason": "Group 8 Naiya SELL"}

    if current_bar['range'] > 0 and current_bar['body'] < 0.4 * current_bar['range'] and (current_bar['close'] - current_bar['low']) > 0.5 * current_bar['range'] and current_bar['low'] <= current_bar['recent_low'] + current_bar['atr']*0.5 and 0 <= current_bar['rsi'] <= 2:
        entry = current_bar['recent_low']
        sl = entry - (2.5 * current_bar['atr'])
        tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
        return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "Doji", "reason": "Group 8 Doji BUY"}
    if current_bar['range'] > 0 and current_bar['body'] < 0.4 * current_bar['range'] and (current_bar['high'] - current_bar['close']) > 0.5 * current_bar['range'] and current_bar['high'] >= current_bar['recent_high'] - current_bar['atr']*0.5 and 74 <= current_bar['rsi'] <= 78 and current_bar['close'] < current_bar['sma50'] and current_bar['close'] < current_bar['sma200']:
        entry = current_bar['recent_high']
        sl = entry + (2.5 * current_bar['atr'])
        tp = entry - ((entry - current_bar['recent_low']) * 1.618)
        return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "Doji", "reason": "Group 8 Doji SELL"}

    return {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 10 -------------
def strategy_20_14_10(rates, tf="M15"):
    return strategy_20_14_7(rates, tf)

# ------------- GROUP 11 -------------
def strategy_20_14_11(rates, tf="M15"):
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    
    s11_res = strategy11.strategy_11(rates, tf)
    if s11_res and s11_res.get("signal") == "BUY":
        return {"signal": "BUY", "entry": s11_res.get("entry", current_bar['close']), "sl": s11_res.get("sl"), "tp": s11_res.get("tp"), "pattern": "Fibo", "reason": "Group 11 Fibo BUY"}
    if s11_res and s11_res.get("signal") == "SELL":
        return {"signal": "SELL", "entry": s11_res.get("entry", current_bar['close']), "sl": s11_res.get("sl"), "tp": s11_res.get("tp"), "pattern": "Fibo", "reason": "Group 11 Fibo SELL"}
        
    if current_bar['range'] > 0 and current_bar['body'] < 0.4 * current_bar['range'] and (current_bar['close'] - current_bar['low']) > 0.5 * current_bar['range'] and current_bar['low'] <= current_bar['recent_low'] + current_bar['atr']*0.5 and 0 <= current_bar['rsi'] <= 2:
        entry = current_bar['recent_low']
        sl = entry - (2.5 * current_bar['atr'])
        tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
        return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "Doji", "reason": "Group 11 Doji BUY"}
    if current_bar['range'] > 0 and current_bar['body'] < 0.4 * current_bar['range'] and (current_bar['high'] - current_bar['close']) > 0.5 * current_bar['range'] and current_bar['high'] >= current_bar['recent_high'] - current_bar['atr']*0.5 and 74 <= current_bar['rsi'] <= 78 and current_bar['close'] < current_bar['sma50'] and current_bar['close'] < current_bar['sma200']:
        entry = current_bar['recent_high']
        sl = entry + (2.5 * current_bar['atr'])
        tp = entry - ((entry - current_bar['recent_low']) * 1.618)
        return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "Doji", "reason": "Group 11 Doji SELL"}

    return {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 15 -------------
def strategy_20_14_15(rates, tf="H1"):
    return strategy_20_14_7(rates, tf)

# ------------- GROUP 17 -------------
def strategy_20_14_17(rates, tf="D1"):
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    
    if current_bar['bull_fvg_10']:
        entry = current_bar['recent_low']
        sl = entry - (2.5 * current_bar['atr'])
        tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
        return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "FVG_D1", "reason": "Group 17 FVG BUY"}
        
    if current_bar['bear_fvg_10']:
        entry = current_bar['recent_high']
        sl = entry + (2.5 * current_bar['atr'])
        tp = entry - ((entry - current_bar['recent_low']) * 1.618)
        return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "FVG_D1", "reason": "Group 17 FVG SELL"}

    return {"signal": "WAIT", "reason": "No Setup"}
