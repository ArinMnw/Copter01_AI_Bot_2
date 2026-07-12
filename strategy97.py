from config import *
import pandas as pd
import numpy as np
from strategy4 import _find_prev_swing_high, _find_prev_swing_low

def detect_s97(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    """
    S97: Fusion (S95 Liquidity Sweep + S96 Volume Profile PoC)
    Trades Liquidity Sweeps that occur near or outside the Volume Profile Point of Control.
    """
    if len(rates) < 60:
        return {"signal": "WAIT", "reason": "Not enough data"}

    # 1. Calculate PoC (from S96)
    df = pd.DataFrame(rates)
    min_p = df['low'].min()
    max_p = df['high'].max()
    
    if max_p == min_p:
         return {"signal": "WAIT", "reason": "No price movement"}

    bins = np.linspace(min_p, max_p, 20)
    vol_profile = np.zeros(len(bins)-1)
    
    lows = df['low'].values
    highs = df['high'].values
    vols = df['tick_volume'].values
    
    for i in range(len(bins)-1):
        mask = (highs >= bins[i]) & (lows <= bins[i+1])
        vol_profile[i] = np.sum(vols[mask])
                
    poc_idx = np.argmax(vol_profile)
    poc_price = (bins[poc_idx] + bins[poc_idx+1]) / 2.0
    
    # Calculate ATR
    atr = sum([max(r["high"] - r["low"], abs(r["high"] - rates[i-1]["close"]), abs(r["low"] - rates[i-1]["close"])) for i, r in enumerate(rates[-15:]) if i > 0]) / 14.0
    
    # 2. Find Swing Points (from S95)
    sh_info = _find_prev_swing_high(rates)
    sl_info = _find_prev_swing_low(rates)

    if not sh_info or not sl_info:
        return {"signal": "WAIT", "reason": "No swing points found"}

    sh_price = sh_info["price"]
    sl_price = sl_info["price"]
    
    last_candle = rates[-1]
    last_high = float(last_candle["high"])
    last_low = float(last_candle["low"])
    last_close = float(last_candle["close"])
    last_open = float(last_candle["open"])
    
    total_range = last_high - last_low
    if total_range <= 0:
        return {"signal": "WAIT", "reason": "Zero range candle"}

    # Extract parameters from cfg
    wick_ratio = float(cfg.get("WICK_RATIO", 0.35)) if cfg else 0.35
    rr = float(cfg.get("RR", 1.5)) if cfg else 1.5
    sl_mult = float(cfg.get("SL_MULT", 0.5)) if cfg else 0.5
    poc_tol = float(cfg.get("POC_TOL", 0.5)) if cfg else 0.5
    
    # SELL Condition: Swept High, Bearish close, Strong Upper Wick
    # AND swept high must be near or ABOVE the PoC (Value is high)
    upper_wick = last_high - max(last_open, last_close)
    if last_high > sh_price and last_close < sh_price and last_close < last_open:
        if upper_wick / total_range >= wick_ratio:
            # Synergy Check: Is the sweep high >= PoC?
            if sh_price >= poc_price - (atr * poc_tol):
                entry = last_close
                sl = last_high + max(1.5, atr * sl_mult)
                risk = sl - entry
                tp = entry - (risk * rr)
                
                return {
                    "signal": "SELL",
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "pattern": "S97 Sweep+PoC 🔴 SELL",
                    "reason": f"Swept High {sh_price:.2f} near PoC {poc_price:.2f}",
                    "candles": [last_candle]
                }
        
    # BUY Condition: Swept Low, Bullish close, Strong Lower Wick
    # AND swept low must be near or BELOW the PoC (Value is low)
    lower_wick = min(last_open, last_close) - last_low
    if last_low < sl_price and last_close > sl_price and last_close > last_open:
        if lower_wick / total_range >= wick_ratio:
            # Synergy Check: Is the sweep low <= PoC?
            if sl_price <= poc_price + (atr * poc_tol):
                entry = last_close
                sl = last_low - max(1.5, atr * sl_mult)
                risk = entry - sl
                tp = entry + (risk * rr)
                
                return {
                    "signal": "BUY",
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "pattern": "S97 Sweep+PoC 🟢 BUY",
                    "reason": f"Swept Low {sl_price:.2f} near PoC {poc_price:.2f}",
                    "candles": [last_candle]
                }

    return {"signal": "WAIT", "reason": "No valid Sweep+PoC detected"}
