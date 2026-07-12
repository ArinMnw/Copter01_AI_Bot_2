from config import *
from strategy4 import _find_prev_swing_high, _find_prev_swing_low

def detect_s95(rates, tf="", dt_bkk=None, cfg=None, htf_ctx=None, **kwargs):
    """
    S95: Liquidity Sweep (SMC)
    Detects if the recent candle sweeps a major swing high/low and reverses with a strong wick rejection.
    """
    if len(rates) < 20:
        return {"signal": "WAIT", "reason": "Not enough data"}
        
    # Time Filter (avoid high volatility / fakeout hours)
    time_filter_enabled = cfg.get("TIME_FILTER_ENABLED", True) if cfg else True
    if time_filter_enabled and dt_bkk:
        if dt_bkk.hour in [10, 11, 12, 13, 18, 19, 20, 21]:
            return {"signal": "WAIT", "reason": f"Blocked by Time Filter (Hour {dt_bkk.hour})"}

    sh_info = None
    sl_info = None

    if tf:
        try:
            from hhll_swing import get_swing_hl_pts
            sh_pt, sl_pt = get_swing_hl_pts(tf)
            if sh_pt:
                sh_candle = next((r for r in rates if int(r["time"]) == int(sh_pt["time"])), None)
                if sh_candle:
                    sh_info = {"price": float(sh_pt["price"]), "time": int(sh_pt["time"]), "candle": sh_candle}
            if sl_pt:
                sl_candle = next((r for r in rates if int(r["time"]) == int(sl_pt["time"])), None)
                if sl_candle:
                    sl_info = {"price": float(sl_pt["price"]), "time": int(sl_pt["time"]), "candle": sl_candle}
        except Exception:
            pass

    if sh_info is None:
        sh_info = _find_prev_swing_high(rates)
    if sl_info is None:
        sl_info = _find_prev_swing_low(rates)

    if not sh_info or not sl_info:
        return {"signal": "WAIT", "reason": "No swing points found"}

    sh_price = sh_info["price"]
    sl_price = sl_info["price"]
    
    # Calculate ATR for dynamic SL buffer
    atr = sum([max(r["high"] - r["low"], abs(r["high"] - rates[i-1]["close"]), abs(r["low"] - rates[i-1]["close"])) for i, r in enumerate(rates[-15:]) if i > 0]) / 14.0
    
    # Check the last closed candle
    last_candle = rates[-1]
    last_high = float(last_candle["high"])
    last_low = float(last_candle["low"])
    last_close = float(last_candle["close"])
    last_open = float(last_candle["open"])
    
    total_range = last_high - last_low
    if total_range <= 0:
        return {"signal": "WAIT", "reason": "Zero range candle"}
        
    # PD Zone Calculation (Equilibrium of last 100 bars)
    eq = None
    if cfg and cfg.get("PD_ZONE_FILTER_ENABLED"):
        recent_bars = rates[-100:]
        highest_100 = max([float(r["high"]) for r in recent_bars])
        lowest_100 = min([float(r["low"]) for r in recent_bars])
        eq = (highest_100 + lowest_100) / 2.0

    # SELL Condition: Swept High, Bearish close, Strong Upper Wick
    upper_wick = last_high - max(last_open, last_close)
    if last_high > sh_price and last_close < sh_price and last_close < last_open:
        if upper_wick / total_range >= 0.35:  # Upper wick must be at least 35% of the candle
            # RSI Momentum Filter (avoid selling into strong uptrend)
            if cfg and cfg.get("RSI_FILTER_ENABLED"):
                import pandas as pd
                df = pd.DataFrame(rates)
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs)).iloc[-1]
                if rsi > float(cfg.get("RSI_SELL_MAX", 60.0)):
                    return {"signal": "WAIT", "reason": f"RSI too high ({rsi:.1f})"}
            
            # PD Zone Filter (SELL must be in Premium)
            if eq is not None:
                if last_close < eq:
                    return {"signal": "WAIT", "reason": f"S95 SELL blocked by PD Zone (Discount)"}
            
            # HTF Trend Filter
            if htf_ctx is not None and cfg and cfg.get("CONFIRMATION_TYPE") == "htf_trend":
                if not htf_ctx.get("trend_down"):
                    return {"signal": "WAIT", "reason": "S95 blocked by HTF Trend (UP)"}
            
            entry = last_close
            sl = last_high + max(1.5, atr * 0.5) # Dynamic buffer above the sweep wick
            risk = sl - entry
            tp = entry - (risk * 1.5) # Fix RR 1:1.5
            
            # ML Model Filter Check
            if cfg and cfg.get("ML_FILTER_ENABLED"):
                import ml_scoring
                prob = ml_scoring.score_signal('XAUUSD.iux', tf, 'SELL', entry, dt_bkk, historical_rates=rates)
                if prob < float(cfg.get("ML_SCORE_THRESHOLD", 0.50)):
                    return {"signal": "WAIT", "reason": f"S95 SELL blocked by ML Score ({prob:.2f})"}
            
            return {
                "signal": "SELL",
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "pattern": "S95 LiqSweep 🔴 SELL",
                "reason": f"Swept Swing High {sh_price:.2f} & rejected.",
                "candles": [last_candle]
            }
        
    # BUY Condition: Swept Low, Bullish close, Strong Lower Wick
    lower_wick = min(last_open, last_close) - last_low
    if last_low < sl_price and last_close > sl_price and last_close > last_open:
        if lower_wick / total_range >= 0.35:  # Lower wick must be at least 35% of the candle
            # RSI Momentum Filter (avoid buying into strong downtrend)
            if cfg and cfg.get("RSI_FILTER_ENABLED"):
                import pandas as pd
                df = pd.DataFrame(rates)
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs)).iloc[-1]
                if rsi < float(cfg.get("RSI_BUY_MIN", 40.0)):
                    return {"signal": "WAIT", "reason": f"RSI too low ({rsi:.1f})"}
            
            # PD Zone Filter (BUY must be in Discount)
            if eq is not None:
                if last_close > eq:
                    return {"signal": "WAIT", "reason": f"S95 BUY blocked by PD Zone (Premium)"}
            
            # HTF Trend Filter
            if htf_ctx is not None and cfg and cfg.get("CONFIRMATION_TYPE") == "htf_trend":
                if not htf_ctx.get("trend_up"):
                    return {"signal": "WAIT", "reason": "S95 blocked by HTF Trend (DOWN)"}
                    
            entry = last_close
            sl = last_low - max(1.5, atr * 0.5) # Dynamic buffer below the sweep wick
            risk = entry - sl
            tp = entry + (risk * 1.5) # Fix RR 1:1.5
            
            # ML Model Filter Check
            if cfg and cfg.get("ML_FILTER_ENABLED"):
                import ml_scoring
                prob = ml_scoring.score_signal('XAUUSD.iux', tf, 'BUY', entry, dt_bkk, historical_rates=rates)
                if prob < float(cfg.get("ML_SCORE_THRESHOLD", 0.50)):
                    return {"signal": "WAIT", "reason": f"S95 BUY blocked by ML Score ({prob:.2f})"}
            
            return {
                "signal": "BUY",
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "pattern": "S95 LiqSweep 🟢 BUY",
                "reason": f"Swept Swing Low {sl_price:.2f} & rejected.",
                "candles": [last_candle]
            }

    return {"signal": "WAIT", "reason": "No valid sweep detected"}
