from config import *
import pandas as pd
import numpy as np

def detect_s96(rates, tf="", dt_bkk=None, cfg=None, htf_ctx=None, **kwargs):
    """
    S96: Volume Profile Point of Control (PoC) Pullback
    Approximates the PoC using candle volume and price. Trades pullbacks to PoC.
    """
    if len(rates) < 60:
        return {"signal": "WAIT", "reason": "Not enough data"}

    # Time Filter (avoid high volatility / fakeout hours)
    time_filter_enabled = cfg.get("TIME_FILTER_ENABLED", True) if cfg else True
    if time_filter_enabled and dt_bkk:
        if dt_bkk.hour in [10, 11, 12, 13, 18, 19, 20, 21]:
            return {"signal": "WAIT", "reason": f"Blocked by Time Filter (Hour {dt_bkk.hour})"}

    # PD Zone Calculation (Equilibrium of last 100 bars)
    eq = None
    if cfg and cfg.get("PD_ZONE_FILTER_ENABLED"):
        recent_bars = rates[-100:]
        highest_100 = max([float(r["high"]) for r in recent_bars])
        lowest_100 = min([float(r["low"]) for r in recent_bars])
        eq = (highest_100 + lowest_100) / 2.0

    df = pd.DataFrame(rates)
    
    # Calculate approximate volume profile (Price x Volume)
    # Since MT5 rates provide 'tick_volume', we use that as a proxy for activity
    # We bin prices into 20 bins
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
                
    # Find the bin with max volume (Point of Control)
    poc_idx = np.argmax(vol_profile)
    poc_price = (bins[poc_idx] + bins[poc_idx+1]) / 2.0
    
    # Check the latest candle action relative to PoC
    last_candle = rates[-1]
    last_high = float(last_candle["high"])
    last_low = float(last_candle["low"])
    last_close = float(last_candle["close"])
    last_open = float(last_candle["open"])
    
    # Calculate ATR
    atr = sum([max(r["high"] - r["low"], abs(r["high"] - rates[i-1]["close"]), abs(r["low"] - rates[i-1]["close"])) for i, r in enumerate(rates[-15:]) if i > 0]) / 14.0
    
    # Extract params
    sl_mult = float(cfg.get("SL_ATR_MULT", 0.5)) if cfg else 0.5
    tp_rr = float(cfg.get("TP_RR", 2.0)) if cfg else 2.0
    poc_tol = float(cfg.get("POC_TOL", 0.3)) if cfg else 0.3
    
    # PoC tolerance (dynamic based on ATR)
    tolerance = max(1.0, atr * poc_tol) 
    
    # If price drops into PoC zone and rejects (closes bullish)
    if last_low <= (poc_price + tolerance) and last_close > poc_price and last_close > last_open:
        # RSI Momentum Filter
        if cfg and cfg.get("RSI_FILTER_ENABLED"):
            # Calculate 14-period RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]
            if rsi < float(cfg.get("RSI_BUY_MIN", 40.0)):
                return {"signal": "WAIT", "reason": f"RSI too low ({rsi:.1f})"}
                
        # HTF Trend Filter check
        if htf_ctx is not None and cfg and cfg.get("CONFIRMATION_TYPE") == "htf_trend":
            if not htf_ctx.get("trend_up"):
                return {"signal": "WAIT", "reason": "htf_trend_against"}
                
        # PD Zone Filter (BUY must be in Discount)
        if eq is not None:
            if last_close > eq:
                return {"signal": "WAIT", "reason": "S96 BUY blocked by PD Zone (Premium)"}
                
        ema50 = df['close'].ewm(span=50, adjust=False).mean().iloc[-1]
        if ema50 < last_close:
            entry = last_close
            sl = last_low - max(1.5, atr * sl_mult)
            risk = entry - sl
            tp = entry + (risk * tp_rr)
            
            # ML Model Filter Check
            if cfg and cfg.get("ML_FILTER_ENABLED"):
                import ml_scoring
                prob = ml_scoring.score_signal('XAUUSD.iux', tf, 'BUY', entry, dt_bkk, historical_rates=rates)
                if prob < float(cfg.get("ML_SCORE_THRESHOLD", 0.50)):
                    return {"signal": "WAIT", "reason": f"S96 BUY blocked by ML Score ({prob:.2f})"}
            
            return {
                "signal": "BUY",
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "pattern": "S96 PoC Pullback 🟢 BUY",
                "reason": f"Pullback to PoC ({poc_price:.2f}) and rejected.",
                "candles": [last_candle]
            }

    # If price rallies into PoC zone and rejects (closes bearish)
    if last_high >= (poc_price - tolerance) and last_close < poc_price and last_close < last_open:
        # RSI Momentum Filter
        if cfg and cfg.get("RSI_FILTER_ENABLED"):
            # Calculate 14-period RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]
            if rsi > float(cfg.get("RSI_SELL_MAX", 60.0)):
                return {"signal": "WAIT", "reason": f"RSI too high ({rsi:.1f})"}
                
        # HTF Trend Filter check
        if htf_ctx is not None and cfg and cfg.get("CONFIRMATION_TYPE") == "htf_trend":
            if not htf_ctx.get("trend_down"):
                return {"signal": "WAIT", "reason": "htf_trend_against"}
                
        # PD Zone Filter (SELL must be in Premium)
        if eq is not None:
            if last_close < eq:
                return {"signal": "WAIT", "reason": "S96 SELL blocked by PD Zone (Discount)"}
                
        ema50 = df['close'].ewm(span=50, adjust=False).mean().iloc[-1]
        if ema50 > last_close:
            entry = last_close
            sl = last_high + max(1.5, atr * sl_mult)
            risk = sl - entry
            tp = entry - (risk * tp_rr)
            
            # ML Model Filter Check
            if cfg and cfg.get("ML_FILTER_ENABLED"):
                import ml_scoring
                prob = ml_scoring.score_signal('XAUUSD.iux', tf, 'SELL', entry, dt_bkk, historical_rates=rates)
                if prob < float(cfg.get("ML_SCORE_THRESHOLD", 0.50)):
                    return {"signal": "WAIT", "reason": f"S96 SELL blocked by ML Score ({prob:.2f})"}
            
            return {
                "signal": "SELL",
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "pattern": "S96 PoC Pullback 🔴 SELL",
                "reason": f"Pullback to PoC ({poc_price:.2f}) and rejected.",
                "candles": [last_candle]
            }
            
    return {"signal": "WAIT", "reason": "No valid PoC Pullback detected"}
