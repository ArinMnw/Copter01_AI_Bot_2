from config import *
import pandas as pd
import numpy as np

def strategy_97(rates, tf=""):
    """
    LTS S97: Volatility Breakout (BB Squeeze)
    Detects when Bollinger Bands squeeze tightly and trades the breakout momentum.
    """
    if len(rates) < 25:
        return {"signal": "WAIT", "reason": "Not enough data"}

    df = pd.DataFrame(rates)
    
    # Calculate Bollinger Bands (20, 2.0)
    sma_20 = df['close'].rolling(20).mean()
    std_20 = df['close'].rolling(20).std()
    upper_bb = sma_20 + (2 * std_20)
    lower_bb = sma_20 - (2 * std_20)
    bb_width = (upper_bb - lower_bb) / sma_20
    
    # Calculate Keltner Channels to identify squeeze (BB inside KC)
    # KC = EMA(20) +/- 1.5 * ATR(20)
    ema_20 = df['close'].ewm(span=20, adjust=False).mean()
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    true_range = np.max(pd.concat([high_low, high_close, low_close], axis=1), axis=1)
    atr_20 = true_range.rolling(20).mean()
    
    upper_kc = ema_20 + (1.5 * atr_20)
    lower_kc = ema_20 - (1.5 * atr_20)
    
    # Squeeze condition: BB is inside KC
    squeeze_on = (upper_bb < upper_kc) & (lower_bb > lower_kc)
    
    last_candle = rates[-1]
    prev_candle = rates[-2]
    
    last_close = float(last_candle["close"])
    last_high = float(last_candle["high"])
    last_low = float(last_candle["low"])
    last_vol = float(last_candle["tick_volume"])
    
    prev_vol = float(prev_candle["tick_volume"])
    
    # Check if we were in a squeeze recently (e.g. within last 3 bars)
    recent_squeeze = squeeze_on.iloc[-4:-1].any()
    
    if recent_squeeze:
        # Breakout UP
        if last_close > upper_bb.iloc[-1] and last_vol > prev_vol * 1.5:
            entry = last_close
            sl = lower_bb.iloc[-1] # SL at opposite band or SMA
            if entry - sl > 5.0: # cap SL size
                sl = entry - 5.0
            tp = entry + (entry - sl) * 2.0 # 1:2 RR
            
            return {
                "signal": "BUY",
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "pattern": "LTS S97 BB Squeeze Breakout 🟢 BUY",
                "reason": "BB Squeeze fired to the upside with high volume.",
                "candles": [last_candle]
            }
            
        # Breakout DOWN
        if last_close < lower_bb.iloc[-1] and last_vol > prev_vol * 1.5:
            entry = last_close
            sl = upper_bb.iloc[-1]
            if sl - entry > 5.0:
                sl = entry + 5.0
            tp = entry - (sl - entry) * 2.0
            
            return {
                "signal": "SELL",
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "pattern": "LTS S97 BB Squeeze Breakout 🔴 SELL",
                "reason": "BB Squeeze fired to the downside with high volume.",
                "candles": [last_candle]
            }
            
    return {"signal": "WAIT", "reason": "No Squeeze Breakout detected"}
