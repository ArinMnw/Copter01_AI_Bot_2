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

def strategy_20_13_17(rates, tf="H1"):
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

    # Z-Score
    sma_20 = df['close'].rolling(20).mean()
    std_20 = df['close'].rolling(20).std()
    df['z_score'] = (df['close'] - sma_20) / std_20
    
    # ADX
    plus_dm = df['high'].diff()
    minus_dm = df['low'].shift() - df['low']
    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
    tr14 = tr.rolling(14).sum()
    plus_di14 = 100 * (pd.Series(plus_dm).rolling(14).sum() / tr14)
    minus_di14 = 100 * (pd.Series(minus_dm).rolling(14).sum() / tr14)
    dx = 100 * (np.abs(plus_di14 - minus_di14) / (plus_di14 + minus_di14))
    df['adx'] = dx.rolling(14).mean()

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
    is_ny_pre_open = (hour == 12 or hour == 13)  # UTC 12:00 = BKK 19:00, UTC 13:00 = BKK 20:00
    is_sydney_open = (hour == 23 or hour == 0)   # UTC 23:00 = BKK 06:00, UTC 00:00 = BKK 07:00
    is_tokyo_buy = (hour == 2)                   # UTC 02:00 = BKK 09:00 signal
    is_late_ny_buy = (hour == 19)                # UTC 19:00 = BKK 02:00 signal
    is_midnight_buy = (hour == 17)               # UTC 17:00 = BKK 00:00 signal
    is_london_open = (hour == 8)                 # UTC 08:00 = BKK 15:00
    is_london_fake = (hour == 9)                 # UTC 09:00 = BKK 16:00
    
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
        if is_ny_pre_open:
            return {"signal": "WAIT", "reason": "NY Pre-Open Trap"}
        if is_sydney_open:
            return {"signal": "WAIT", "reason": "Sydney Open Trap"}
        if is_tokyo_buy:
            return {"signal": "WAIT", "reason": "Tokyo Open Trap (BUY)"}
        if is_late_ny_buy:
            return {"signal": "WAIT", "reason": "Late NY Trap (BUY)"}
        if is_midnight_buy:
            return {"signal": "WAIT", "reason": "Midnight Trap (BUY)"}
        if is_london_open:
            return {"signal": "WAIT", "reason": "London Open Trap"}
        if is_london_fake:
            return {"signal": "WAIT", "reason": "London Fakeout Trap"}
            
        if current_bar['rsi'] < 35:
            return {"signal": "WAIT", "reason": f"RSI too low ({current_bar['rsi']:.1f})"}
            
        entry_price = current_bar['close']
        sweep_bottom = min(recent_3['low'].min(), current_bar['low'])
        if current_bar['z_score'] > 0.0 and current_bar['adx'] > 30.0:
            return {"signal": "WAIT", "reason": f"BUY Trend/Z Block (Z={current_bar['z_score']:.2f}, ADX={current_bar['adx']:.1f})"}
        sl = sweep_bottom - config.SL_BUFFER(current_bar['atr'])
        fuel_multiplier = get_fuel_multiplier(tf, target_tf_buy)
        fuel = current_bar['atr'] * active_mode * fuel_multiplier
        tp = sweep_bottom + fuel
        return {
            "signal": "BUY",
            "entry": entry_price,
            "sl": sl,
            "tp": tp,
            "pattern": "S20.13.17 PA Confirmed BUY",
            "reason": f"Sweep {local_low:.2f} | No Trend | TP {tp:.2f}"
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
        if is_ny_pre_open:
            return {"signal": "WAIT", "reason": "NY Pre-Open Trap"}
        if is_sydney_open:
            return {"signal": "WAIT", "reason": "Sydney Open Trap"}
        if is_london_open:
            return {"signal": "WAIT", "reason": "London Open Trap"}
        if is_london_fake:
            return {"signal": "WAIT", "reason": "London Fakeout Trap"}
            
        if current_bar['rsi'] > 60:
            return {"signal": "WAIT", "reason": f"RSI too high ({current_bar['rsi']:.1f})"}
            
        entry_price = current_bar['close']
        sweep_top = max(recent_3['high'].max(), current_bar['high'])
        if (current_bar['z_score'] < 0.0 and current_bar['adx'] > 50.0) or (current_bar['close'] - current_bar['ema_50'] > 100.0):
            return {"signal": "WAIT", "reason": f"SELL Trend/Z Block (Z={current_bar['z_score']:.2f}, ADX={current_bar['adx']:.1f})"}
        sl = sweep_top + config.SL_BUFFER(current_bar['atr'])
        fuel_multiplier = get_fuel_multiplier(tf, target_tf_sell)
        fuel = current_bar['atr'] * active_mode * fuel_multiplier
        tp = sweep_top - fuel
        return {
            "signal": "SELL",
            "entry": entry_price,
            "sl": sl,
            "tp": tp,
            "pattern": "S20.13.17 PA Confirmed SELL",
            "reason": f"Sweep {local_high:.2f} | No Trend | TP {tp:.2f}"
        }

    return {"signal": "WAIT", "reason": "No Setup"}
