import os

path = r"d:\Project\Copter01_AI_Bot_2\strategy\s20.13\strategy20_13.py"

content = """import pandas as pd
import numpy as np
import config

def strategy_20_13(rates, tf="M1"):
    if rates is None or len(rates) < 20:
        return {"signal": "WAIT", "reason": "Not enough data"}

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = df[['high', 'low', 'close']].copy()
    tr['tr'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr['tr'].rolling(window=14).mean()
    
    current_bar = df.iloc[-1]
    
    if pd.isna(current_bar['atr']):
        return {"signal": "WAIT", "reason": "ATR not ready"}

    # Use a 3-bar lookback for local swing (minor sweep)
    lookback_bars = df.iloc[-4:-1]
    if len(lookback_bars) < 3:
        return {"signal": "WAIT", "reason": "Not enough bars"}
        
    local_low = lookback_bars['low'].min()
    local_high = lookback_bars['high'].max()
    
    # Active mode
    active_mode = getattr(config, "S20_13_ACTIVE_MODE", 2.6)
    
    # Check BUY Sweep
    if current_bar['low'] < local_low and current_bar['close'] > local_low and current_bar['close'] > current_bar['open']:
        entry_price = current_bar['close']
        sl = current_bar['low'] - config.SL_BUFFER(current_bar['atr'])
        
        fuel_multiplier = getattr(config, "S20_13_FUEL_MULTIPLIER", 3.42)
        fuel = current_bar['atr'] * active_mode * fuel_multiplier
        tp = local_low + fuel
        
        return {
            "signal": "BUY",
            "entry": entry_price,
            "sl": sl,
            "tp": tp,
            "pattern": "S20.13 Quant Fuel BUY",
            "reason": f"Sweep Low {local_low:.2f} | Fuel {fuel:.2f}"
        }
        
    # Check SELL Sweep
    if current_bar['high'] > local_high and current_bar['close'] < local_high and current_bar['close'] < current_bar['open']:
        entry_price = current_bar['close']
        sl = current_bar['high'] + config.SL_BUFFER(current_bar['atr'])
        
        fuel_multiplier = 4.7 # Default for SELL per video 2
        fuel = current_bar['atr'] * active_mode * fuel_multiplier
        tp = local_high - fuel
        
        return {
            "signal": "SELL",
            "entry": entry_price,
            "sl": sl,
            "tp": tp,
            "pattern": "S20.13 Quant Fuel SELL",
            "reason": f"Sweep High {local_high:.2f} | Fuel {fuel:.2f}"
        }
        
    return {"signal": "WAIT", "reason": "No Setup"}
"""

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed strategy20_13.py")
