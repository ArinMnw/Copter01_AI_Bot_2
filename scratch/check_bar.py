import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
try:
    import config
    from strategy.s20_13.strategy20_13 import strategy_20_13
except:
    pass

def check_fuel_at_bar(target_time_str, symbol, tf_mt5):
    if not mt5.initialize():
        print("MT5 init failed")
        return

    # Parse target time. Assume it is MT5 server time (which is UTC+6 usually for IUX)
    # The user said 18-07-2569 03:00 -> 2026-07-18 03:00
    target_dt = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M")
    
    # We will fetch 50 bars before this time + 1 bar at this time
    # to calculate ATR and swing low.
    rates = mt5.copy_rates_from(symbol, tf_mt5, target_dt, 30)
    
    if rates is None or len(rates) == 0:
        print(f"No rates found for {symbol} at {target_dt}")
        return
        
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Check if the requested bar exists in the dataset
    bar = df[df['time'] == target_dt]
    if bar.empty:
        print(f"Bar at {target_dt} not found for {symbol}. Closest bars:")
        print(df.tail(3)[['time', 'open', 'high', 'low', 'close']])
        
    # Calculate ATR (14)
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = df[['high', 'low', 'close']].copy()
    tr['tr'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr['tr'].rolling(window=14).mean()
    
    # Assuming Fuel Multiplier = 3.42
    fuel_multiplier = 3.42
    df['fuel'] = df['atr'] * fuel_multiplier
    
    print(f"\n--- Data for {symbol} at H1 around {target_dt} ---")
    res_df = df.tail(5)[['time', 'open', 'high', 'low', 'close', 'atr', 'fuel']]
    print(res_df.to_string(index=False))
    
    if not bar.empty:
        idx = bar.index[0]
        # Lookback for swing low (exclude current and last 2)
        if idx >= 20:
            lookback = df.iloc[idx-20:idx-2]
            swing_low = lookback['low'].min()
            current_bar = df.iloc[idx]
            print(f"\nSwing Low (last 20 bars): {swing_low}")
            print(f"Current Low: {current_bar['low']}, Current Close: {current_bar['close']}")
            
            sweep = current_bar['low'] < swing_low
            rejection = current_bar['close'] > swing_low
            bullish = current_bar['close'] > current_bar['open']
            
            print(f"Sweep: {sweep}, Rejection: {rejection}, Bullish: {bullish}")
            if sweep and rejection and bullish:
                print("==> SIGNAL: BUY SETUP MATCHED!")
            else:
                print("==> SIGNAL: NO MATCH")
                
    mt5.shutdown()

if __name__ == "__main__":
    # check multiple symbols because we don't know what symbol the user meant
    symbols = ["XAUUSD", "BTCUSD", "ETHUSD", "US30", "US500"]
    for s in symbols:
        check_fuel_at_bar("2026-07-18 03:00", s, mt5.TIMEFRAME_H1)
