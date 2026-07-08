import mt5_worker as mt5
import pandas as pd
import numpy as np

def get_volatility_scalar(symbol, timeframe=mt5.TIMEFRAME_D1, lookback=14):
    """
    Calculates a volatility scalar for Dynamic Weighting.
    If current ATR is higher than the historical average ATR, reduce the scalar to < 1.0.
    Returns a scalar between 0.25 and 1.0 to multiply the LTS weight.
    """
    if mt5.terminal_info() is None:
        return 1.0
        
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback * 2)
    if rates is None or len(rates) < lookback:
        return 1.0
        
    df = pd.DataFrame(rates)
    df['tr'] = np.maximum(df['high'] - df['low'], 
                          np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                     abs(df['low'] - df['close'].shift(1))))
    
    df['atr'] = df['tr'].rolling(window=lookback).mean()
    
    current_atr = df['atr'].iloc[-1]
    hist_atr = df['atr'].mean()
    
    if pd.isna(current_atr) or pd.isna(hist_atr) or hist_atr == 0:
        return 1.0
        
    # Volatility Ratio
    ratio = current_atr / hist_atr
    
    # If volatility is high (ratio > 1.2), scale down weight
    # Example: ratio 1.5 -> scalar 0.66
    if ratio > 1.2:
        scalar = 1.0 / ratio
        return max(0.25, min(1.0, scalar))
        
    return 1.0
