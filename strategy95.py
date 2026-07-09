from config import *
from strategy4 import _find_prev_swing_high, _find_prev_swing_low

def strategy_95(rates, tf=""):
    """
    LTS S95: Liquidity Sweep (SMC)
    Detects if the recent candle sweeps a major swing high/low and reverses (closes inside the range).
    """
    if len(rates) < 10:
        return {"signal": "WAIT", "reason": "Not enough data"}

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
    
    # Check the last closed candle
    last_candle = rates[-1]
    last_high = float(last_candle["high"])
    last_low = float(last_candle["low"])
    last_close = float(last_candle["close"])
    last_open = float(last_candle["open"])
    
    # SELL Condition: Swept High, but closed below High (Bearish reversal)
    if last_high > sh_price and last_close < sh_price and last_close < last_open:
        # Sweep detected!
        entry = last_close
        sl = last_high + 2.0 # 20 pips buffer above the sweep wick
        tp = sl_price # Target the swing low
        
        return {
            "signal": "SELL",
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "pattern": "LTS S95 Liquidity Sweep 🔴 SELL",
            "reason": f"Swept Swing High at {sh_price:.2f} and closed bearish at {last_close:.2f}.",
            "candles": [last_candle]
        }
        
    # BUY Condition: Swept Low, but closed above Low (Bullish reversal)
    if last_low < sl_price and last_close > sl_price and last_close > last_open:
        entry = last_close
        sl = last_low - 2.0 # 20 pips buffer below the sweep wick
        tp = sh_price # Target the swing high
        
        return {
            "signal": "BUY",
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "pattern": "LTS S95 Liquidity Sweep 🟢 BUY",
            "reason": f"Swept Swing Low at {sl_price:.2f} and closed bullish at {last_close:.2f}.",
            "candles": [last_candle]
        }

    return {"signal": "WAIT", "reason": "No sweep detected"}
