import pandas as pd
import numpy as np
import config
import joblib
import os
import sys

# Append base strategy dir to path so we can import other strategies
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(base_dir, '..', '..')))

import strategy.s1.strategy1 as strategy1
import strategy.s9.strategy9 as strategy9
import strategy.s11.strategy11 as strategy11
import strategy.s20.13.strategy20_13_24 as strategy20_13_24

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

def strategy_20_14(rates, tf="H1"):
    if rates is None or len(rates) < 55:
        return {"signal": "WAIT", "reason": "Not enough data"}

    load_models()

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # 1. ATR
    hl = df['high'] - df['low']
    hc = np.abs(df['high'] - df['close'].shift())
    lc = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()
    
    # 2. RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 3. SMAs
    df['sma12'] = df['close'].rolling(window=12).mean()
    df['sma20'] = df['close'].rolling(window=20).mean()
    df['sma50'] = df['close'].rolling(window=50).mean()
    df['sma200'] = df['close'].rolling(window=200).mean()
    
    df['dist_sma50'] = df['close'] - df['sma50']
    df['dist_sma200'] = df['close'] - df['sma200']
    
    # 4. Swings
    df['recent_low'] = df['low'].rolling(window=20).min().shift(1)
    df['recent_high'] = df['high'].rolling(window=20).max().shift(1)
    df['recent_low_50'] = df['low'].rolling(window=50).min().shift(1)
    df['recent_high_50'] = df['high'].rolling(window=50).max().shift(1)
    df['rsi_low'] = df['rsi'].rolling(window=20).min().shift(1)
    df['rsi_high'] = df['rsi'].rolling(window=20).max().shift(1)
    
    # 5. Candles
    df['body'] = np.abs(df['close'] - df['open'])
    df['range'] = df['high'] - df['low']
    df['doji'] = (df['body'] <= df['range'] * 0.25)
    
    df['engulfing_bull'] = (df['close'] > df['open']) & (df['open'].shift(1) > df['close'].shift(1)) & (df['open'] <= df['close'].shift(1)) & (df['close'] > df['open'].shift(1))
    df['engulfing_bear'] = (df['close'] < df['open']) & (df['open'].shift(1) < df['close'].shift(1)) & (df['open'] >= df['close'].shift(1)) & (df['close'] < df['open'].shift(1))
    
    df['naiya_buy_base'] = df['doji'].shift(1) & df['engulfing_bull']
    df['naiya_sell_base'] = df['doji'].shift(1) & df['engulfing_bear']
    
    df['bull_fvg_raw'] = df['high'].shift(2) < df['low']
    df['bear_fvg_raw'] = df['low'].shift(2) > df['high']
    df['bull_fvg_10'] = df['bull_fvg_raw'].rolling(window=10).max() > 0
    df['bear_fvg_10'] = df['bear_fvg_raw'].rolling(window=10).max() > 0

    current_bar = df.iloc[-1]
    
    if pd.isna(current_bar['atr']) or pd.isna(current_bar['rsi']):
        return {"signal": "WAIT", "reason": "Indicators not ready"}

    patterns_buy = []
    patterns_sell = []
    
    # ML Features
    f = [current_bar['rsi'], current_bar['atr'], current_bar['dist_sma50'], current_bar['dist_sma200'], current_bar['body'], current_bar['range']]
    fvg_buy_ml = get_ml_pred("fvg_buy_v22.pkl", f)
    fvg_sell_ml = get_ml_pred("fvg_sell_v22.pkl", f)
    naiya_buy_ml = get_ml_pred("naiya_buy_v22.pkl", f)
    naiya_sell_ml = get_ml_pred("naiya_sell_v22.pkl", f)
    
    # Fibo Zones
    swing_h = current_bar['recent_high_50']
    swing_l = current_bar['recent_low_50']
    fibo_38_2 = swing_l + (swing_h - swing_l) * 0.382
    fibo_61_8 = swing_l + (swing_h - swing_l) * 0.618
    
    # Get External Strategy Signals
    s1_res = strategy1.strategy_1(rates, tf)
    if s1_res and s1_res.get("signal") in ["BUY", "SELL"]:
        strategy11.record_s1_pattern(tf, s1_res["signal"], rates, rates[-1]["time"])
    s11_res = strategy11.strategy_11(rates, tf)
    s9_res = strategy9.strategy_9(rates, tf)
    atr_res = strategy20_13_24.evaluate_bar(df, len(df)-1, tf=tf)

    # ------------------ BUY Logic ------------------
    if current_bar['bull_fvg_10']:
        if fvg_buy_ml == 1 or current_bar['rsi'] > 70:
            if 15.0 <= current_bar['rsi'] <= 68.0 and current_bar['atr'] >= 7.0:
                if current_bar['recent_low'] < fibo_38_2 or current_bar['rsi'] > 70:
                    patterns_buy.append("FVG")
                    
    if current_bar['naiya_buy_base']:
        if naiya_buy_ml == 1 or current_bar['rsi'] < 30:
            if current_bar['recent_low'] < fibo_38_2 or current_bar['rsi'] < 30:
                patterns_buy.append("Naiya")
                
    if s11_res and s11_res.get("signal") == "BUY":
        patterns_buy.append("Fibo")
        
    for b in range(2, 45):
        b_bar = df.iloc[-b]
        if b_bar['close'] > b_bar['open']:
            rng = b_bar['high'] - b_bar['low']
            if rng > 0:
                krh3 = b_bar['high'] - (rng * 5.165)
                if abs(current_bar['low'] - krh3) < 3.0 and current_bar['close'] > current_bar['open']:
                    patterns_buy.append("Fibo")
                    break
                    
    if s9_res and s9_res.get("signal") == "BUY":
        if 10.0 <= current_bar['rsi'] <= 34.0 and current_bar['atr'] >= 8.0:
            patterns_buy.append("Div")
            
    if atr_res and atr_res.get("signal") == "BUY":
        patterns_buy.append("ATR")
        
    if current_bar['range'] > 0 and current_bar['body'] < 0.4 * current_bar['range'] and (current_bar['close'] - current_bar['low']) > 0.5 * current_bar['range'] and current_bar['low'] <= current_bar['recent_low'] + current_bar['atr']*0.5 and 0 <= current_bar['rsi'] <= 2:
        patterns_buy.append("Doji")
        
    if current_bar['low'] <= current_bar['sma12'] and current_bar['close'] > current_bar['sma12'] and 0 <= current_bar['rsi'] <= 18:
        patterns_buy.append("MA12")

    # ------------------ SELL Logic ------------------
    if current_bar['bear_fvg_10']:
        if fvg_sell_ml == 1 or current_bar['rsi'] < 30:
            if 10.0 <= current_bar['rsi'] <= 77.0 and current_bar['atr'] >= 10.0:
                if current_bar['recent_high'] > fibo_61_8 or current_bar['rsi'] < 30:
                    patterns_sell.append("FVG")
                    
    if current_bar['naiya_sell_base']:
        if naiya_sell_ml == 1 or current_bar['rsi'] > 70:
            if current_bar['recent_high'] > fibo_61_8 or current_bar['rsi'] > 70:
                patterns_sell.append("Naiya")
                
    if s11_res and s11_res.get("signal") == "SELL":
        patterns_sell.append("Fibo")
        
    for b in range(2, 45):
        b_bar = df.iloc[-b]
        if b_bar['close'] < b_bar['open']:
            rng = b_bar['high'] - b_bar['low']
            if rng > 0:
                krh3 = b_bar['low'] + rng * 5.165
                if abs(current_bar['high'] - krh3) < 3.0 and current_bar['close'] < current_bar['open']:
                    patterns_sell.append("Fibo")
                    break
                    
    if s9_res and s9_res.get("signal") == "SELL":
        if 66.0 <= current_bar['rsi'] <= 90.0 and current_bar['atr'] >= 8.0:
            patterns_sell.append("Div")
            
    if atr_res and atr_res.get("signal") == "SELL":
        patterns_sell.append("ATR")
        
    if current_bar['range'] > 0 and current_bar['body'] < 0.4 * current_bar['range'] and (current_bar['high'] - current_bar['close']) > 0.5 * current_bar['range'] and current_bar['high'] >= current_bar['recent_high'] - current_bar['atr']*0.5 and 74 <= current_bar['rsi'] <= 78 and current_bar['close'] < current_bar['sma50'] and current_bar['close'] < current_bar['sma200']:
        patterns_sell.append("Doji")
        
    if current_bar['high'] >= current_bar['sma12'] and current_bar['close'] < current_bar['sma12'] and 74 <= current_bar['rsi'] <= 76 and current_bar['close'] < current_bar['sma50']:
        patterns_sell.append("MA12")

    if patterns_buy:
        pat = "/".join(set(patterns_buy))
        entry_price = current_bar['recent_low']
        sl = current_bar['recent_low'] - (2.5 * current_bar['atr'])
        tp = entry_price + ((current_bar['recent_high'] - current_bar['recent_low']) * 1.618)
        return {
            "signal": "BUY",
            "entry": entry_price,
            "sl": sl,
            "tp": tp,
            "pattern": pat,
            "reason": f"{pat} | RSI {current_bar['rsi']:.2f}"
        }
        
    if patterns_sell:
        pat = "/".join(set(patterns_sell))
        entry_price = current_bar['recent_high']
        sl = current_bar['recent_high'] + (2.5 * current_bar['atr'])
        tp = entry_price - ((current_bar['recent_high'] - current_bar['recent_low']) * 1.618)
        return {
            "signal": "SELL",
            "entry": entry_price,
            "sl": sl,
            "tp": tp,
            "pattern": pat,
            "reason": f"{pat} | RSI {current_bar['rsi']:.2f}"
        }

    return {"signal": "WAIT", "reason": "No Setup"}
