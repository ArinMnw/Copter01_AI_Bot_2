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
import s20_14_s11 as strategy11
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
        df_feat = pd.DataFrame([features], columns=model.feature_names_in_)
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
    if tf not in ["H1"]: return {"signal": "WAIT"} # Group 2 targets Inst_Gap H1 only
    
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
    if tf not in ["M30", "D1"]: return {"signal": "WAIT"} # Fibo and FVG on M30, D1
    
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
    if tf not in ["H1"]: return {"signal": "WAIT"} # Naiya and Doji on H1
    
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
    if tf not in ["H1"]: return {"signal": "WAIT"}
    
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
    if tf not in ["H1", "D1"]: return {"signal": "WAIT"} # FVG, GapSweep
    
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
    if tf not in ["H1"]: return {"signal": "WAIT"}
    
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
    if tf not in ["H1"]: return {"signal": "WAIT"}
    
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
    if tf not in ["H1"]: return {"signal": "WAIT"}
    
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

# ------------- GROUP 24 -------------
def strategy_20_14_24(rates, tf="H1"):
    return strategy_20_14_19(rates, tf) # Same as 19 based on target_tfs
