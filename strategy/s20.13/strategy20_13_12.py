import pandas as pd
import numpy as np
import config
from mt5_utils import now_bkk

def get_fuel_multiplier(current_tf, target_tf):
    tf_minutes = {
        "M1": 1, "M5": 5, "M15": 15, "M30": 30,
        "H1": 60, "H4": 240, "H12": 720, "D1": 1440
    }
    cur_mins = tf_minutes.get(current_tf, 60)
    tgt_mins = tf_minutes.get(target_tf, 720) # Default H12
    return np.sqrt(tgt_mins / cur_mins)

def strategy_20_13_12(rates, tf="H1"):
    if rates is None or len(rates) < 20:
        return {"signal": "WAIT", "reason": "Not enough data"}

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Calculate ATR
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()
    
    # Calculate EMA 50 and 200
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # Calculate RSI 14
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    current_bar = df.iloc[-1]
    prev_bar = df.iloc[-2]
    
    if pd.isna(current_bar['atr']) or pd.isna(current_bar['rsi']) or pd.isna(current_bar['ema_200']):
        return {"signal": "WAIT", "reason": "Indicators not ready"}

    lookback_bars = df.iloc[-15:-4]
    local_low = lookback_bars['low'].min()
    local_high = lookback_bars['high'].max()
    
    active_mode = getattr(config, "S20_13_ACTIVE_MODE", 2.6)
    target_tf_buy = getattr(config, "S20_13_TARGET_TF_BUY", "H12")
    target_tf_sell = getattr(config, "S20_13_TARGET_TF_SELL", "D1")
    
    current_time = pd.to_datetime(current_bar['time'], unit='s')
    hour = current_time.hour
    is_london_open = (hour == 8 or hour == 9)
    
    is_uptrend = current_bar['close'] > current_bar['ema_50'] and current_bar['ema_50'] > current_bar['ema_200']
    is_downtrend = current_bar['close'] < current_bar['ema_50'] and current_bar['ema_50'] < current_bar['ema_200']
    
    # Base Filter 20.13.3 (Engulfing Range ATR)
    cur_range = current_bar['high'] - current_bar['low']
    is_strong_range = cur_range >= (0.8 * current_bar['atr'])

    # -------------------------------------------------------------
    # BUY PA CONFIRMATION (CHoCH / Engulfing)
    # -------------------------------------------------------------
    recent_3 = df.iloc[-4:-1]
    sweep_buy = recent_3['low'].min() < local_low
    engulf_buy = current_bar['close'] > prev_bar['high']
    
    instant_sweep_buy = current_bar['low'] < local_low and current_bar['close'] > prev_bar['high']
    
    if (sweep_buy and engulf_buy) or instant_sweep_buy:
        if not is_strong_range:
            return {"signal": "WAIT", "reason": "Engulfing Range < 0.8 ATR"}
        if is_london_open:
            return {"signal": "WAIT", "reason": "London Open Trap"}
            
        # IDEA 12: Buy Dips (Avoid Buy in Downtrend)
        if is_downtrend:
            return {"signal": "WAIT", "reason": "Avoid Buy in Downtrend"}
            
        if current_bar['rsi'] < 35:
            return {"signal": "WAIT", "reason": f"RSI too low ({current_bar['rsi']:.1f})"}
            
        entry_price = current_bar['close']
        sweep_bottom = min(recent_3['low'].min(), current_bar['low'])
        sl = sweep_bottom - config.SL_BUFFER(current_bar['atr'])
        fuel_multiplier = get_fuel_multiplier(tf, target_tf_buy)
        fuel = current_bar['atr'] * active_mode * fuel_multiplier
        tp = sweep_bottom + fuel
        return {
            "signal": "BUY",
            "entry": entry_price,
            "sl": sl,
            "tp": tp,
            "pattern": "S20.13.12 PA Confirmed BUY",
            "reason": f"Sweep {local_low:.2f} | Buy Dip | TP {tp:.2f}"
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
        if is_london_open:
            return {"signal": "WAIT", "reason": "London Open Trap"}
            
        # IDEA 12: Sell Rallies (Avoid Sell in Uptrend)
        if is_uptrend:
            return {"signal": "WAIT", "reason": "Avoid Sell in Uptrend"}
            
        if current_bar['rsi'] > 55:
            return {"signal": "WAIT", "reason": f"RSI too high ({current_bar['rsi']:.1f})"}
            
        entry_price = current_bar['close']
        sweep_top = max(recent_3['high'].max(), current_bar['high'])
        sl = sweep_top + config.SL_BUFFER(current_bar['atr'])
        fuel_multiplier = get_fuel_multiplier(tf, target_tf_sell)
        fuel = current_bar['atr'] * active_mode * fuel_multiplier
        tp = sweep_top - fuel
        return {
            "signal": "SELL",
            "entry": entry_price,
            "sl": sl,
            "tp": tp,
            "pattern": "S20.13.12 PA Confirmed SELL",
            "reason": f"Sweep {local_high:.2f} | Sell Rally | TP {tp:.2f}"
        }

    return {"signal": "WAIT", "reason": "No Setup"}
