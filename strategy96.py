from config import *
import pandas as pd
import numpy as np

def strategy_96(rates, tf=""):
    """
    LTS S96: Volume Profile Point of Control (PoC) Pullback
    Approximates the PoC using candle volume and price. Trades pullbacks to PoC.
    """
    if len(rates) < 50:
        return {"signal": "WAIT", "reason": "Not enough data"}

    df = pd.DataFrame(rates)
    
    # Calculate approximate volume profile (Price x Volume)
    # Since MT5 rates provide 'tick_volume', we use that as a proxy for activity
    # We bin prices into 20 bins
    min_p = df['low'].min()
    max_p = df['high'].min() # wait, max_p = df['high'].max()
    max_p = df['high'].max()
    
    if max_p == min_p:
         return {"signal": "WAIT", "reason": "No price movement"}

    bins = np.linspace(min_p, max_p, 20)
    vol_profile = np.zeros(len(bins)-1)
    
    for _, row in df.iterrows():
        # Distribute volume across bins that intersect this candle
        low = row['low']
        high = row['high']
        vol = row['tick_volume']
        
        for i in range(len(bins)-1):
            b_start = bins[i]
            b_end = bins[i+1]
            # Check overlap
            if high >= b_start and low <= b_end:
                vol_profile[i] += vol
                
    # Find the bin with max volume (Point of Control)
    poc_idx = np.argmax(vol_profile)
    poc_price = (bins[poc_idx] + bins[poc_idx+1]) / 2.0
    
    # Check the latest candle action relative to PoC
    last_candle = rates[-1]
    last_high = float(last_candle["high"])
    last_low = float(last_candle["low"])
    last_close = float(last_candle["close"])
    last_open = float(last_candle["open"])
    
    # PoC tolerance (e.g. 10 pips)
    tolerance = 1.0 
    
    # If price drops into PoC zone and rejects (closes bullish)
    if last_low <= (poc_price + tolerance) and last_close > poc_price and last_close > last_open:
        # Check if the overall trend is UP (EMA 50)
        ema50 = df['close'].ewm(span=50, adjust=False).mean().iloc[-1]
        if last_close > ema50:
            entry = last_close
            sl = last_low - 2.0
            tp = last_high + (entry - sl) * 1.5 # 1.5 RR
            return {
                "signal": "BUY",
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "pattern": "LTS S96 PoC Pullback 🟢 BUY",
                "reason": f"Pullback to PoC ({poc_price:.2f}) and rejected.",
                "candles": [last_candle]
            }

    # If price rallies into PoC zone and rejects (closes bearish)
    if last_high >= (poc_price - tolerance) and last_close < poc_price and last_close < last_open:
        ema50 = df['close'].ewm(span=50, adjust=False).mean().iloc[-1]
        if last_close < ema50:
            entry = last_close
            sl = last_high + 2.0
            tp = last_low - (sl - entry) * 1.5
            return {
                "signal": "SELL",
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "pattern": "LTS S96 PoC Pullback 🔴 SELL",
                "reason": f"Pullback to PoC ({poc_price:.2f}) and rejected.",
                "candles": [last_candle]
            }
            
    return {"signal": "WAIT", "reason": "No PoC Pullback detected"}
