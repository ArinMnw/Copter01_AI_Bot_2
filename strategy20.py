import config
import hhll_swing

def _get_recent_fvg(rates, signal: str):
    """
    Find the most recent FVG that hasn't been completely filled.
    BUY signal needs Bullish FVG (Demand): L3 > H1.
    SELL signal needs Bearish FVG (Supply): H3 < L1.
    """
    # Check last 20 candles
    n = len(rates)
    for i in range(n - 4, max(-1, n - 20), -1):
        c1, c2, c3 = rates[i], rates[i+1], rates[i+2]
        if signal == "BUY":
            if c3['low'] > c1['high']:  # Bullish FVG
                # Check if it was filled by subsequent candles
                filled = False
                for j in range(i+3, n):
                    if rates[j]['low'] <= c1['high']:
                        filled = True
                        break
                if not filled:
                    return (c1['high'], c3['low']) # FVG Top, FVG Bot
        else:
            if c3['high'] < c1['low']:  # Bearish FVG
                filled = False
                for j in range(i+3, n):
                    if rates[j]['high'] >= c1['low']:
                        filled = True
                        break
                if not filled:
                    return (c3['high'], c1['low']) # FVG Top, FVG Bot
    return None

def _is_sideway_trap(rates, signal: str):
    """
    Detect if the recent price action swept a local High/Low and reversed.
    For BUY: Swept a local Low, then reversed up.
    For SELL: Swept a local High, then reversed down.
    """
    n = len(rates)
    if n < 10: return False
    
    # We look at the trigger candle (n-1 or n-2)
    current_low = min(rates[-1]['low'], rates[-2]['low'])
    current_high = max(rates[-1]['high'], rates[-2]['high'])
    
    # Look back 5-10 candles to find a local swing
    if signal == "BUY":
        local_lows = [rates[i]['low'] for i in range(n-10, n-3)]
        if not local_lows: return False
        min_local_low = min(local_lows)
        # If current low swept the min local low, it's a trap
        if current_low < min_local_low:
            return True
    else:
        local_highs = [rates[i]['high'] for i in range(n-10, n-3)]
        if not local_highs: return False
        max_local_high = max(local_highs)
        if current_high > max_local_high:
            return True
    return False

def strategy_20(rates, tf=None):
    """
    Strategy 20: All in 4s Variants
    S20.1: Classic (2 bars engulfing)
    S20.2: Tainted (3 bars delayed engulfing)
    S20.3: HTF Fibo Alignment
    S20.4: FVG / OB Bounce
    S20.5: Sideway Trap (Liquidity Sweep)
    """
    res = {"signal": "WAIT", "reason": ""}
    
    if len(rates) < 4:
        res["reason"] = "Not enough data"
        return res
        
    if tf and tf not in config.S20_ALLOWED_TFS:
        res["reason"] = f"TF {tf} not allowed for S20"
        return res

    bar_prev2 = rates[-3]
    bar_prev1 = rates[-2]
    bar_curr  = rates[-1]

    # --- S20.1 Classic ---
    # BUY: Red wick lower, Green closes above Red wick
    is_red1 = bar_prev1['close'] < bar_prev1['open']
    is_green2 = bar_curr['close'] > bar_curr['open']
    
    classic_buy = (is_red1 and is_green2 and 
                   bar_prev1['low'] < bar_prev1['close'] and 
                   bar_curr['close'] > bar_prev1['high'])
                   
    classic_sell = (not is_red1 and not is_green2 and 
                    bar_prev1['high'] > bar_prev1['close'] and 
                    bar_curr['close'] < bar_prev1['low'])

    # --- S20.2 Tainted ---
    # BUY: Red wick lower, Green 1 doesn't engulf, Green 2 engulfs
    is_red_prev2 = bar_prev2['close'] < bar_prev2['open']
    is_green_prev1 = bar_prev1['close'] > bar_prev1['open']
    is_green_curr = bar_curr['close'] > bar_curr['open']
    
    tainted_buy = (is_red_prev2 and is_green_prev1 and is_green_curr and 
                   bar_prev2['low'] < bar_prev2['close'] and 
                   bar_prev1['close'] <= bar_prev2['high'] and 
                   bar_curr['close'] > bar_prev2['high'])
                   
    tainted_sell = (not is_red_prev2 and not is_green_prev1 and not is_green_curr and 
                    bar_prev2['high'] > bar_prev2['close'] and 
                    bar_prev1['close'] >= bar_prev2['low'] and 
                    bar_curr['close'] < bar_prev2['low'])

    signal = None
    sub_pattern = None
    entry_bar = None
    ref_bar = None # แท่งตั้งต้นที่ใช้อ้างอิง High/Low สำหรับ Fibo
    
    if classic_buy:
        signal = "BUY"
        sub_pattern = "S20.1"
        entry_bar = bar_curr
        ref_bar = bar_prev1
    elif classic_sell:
        signal = "SELL"
        sub_pattern = "S20.1"
        entry_bar = bar_curr
        ref_bar = bar_prev1
    elif tainted_buy:
        signal = "BUY"
        sub_pattern = "S20.2"
        entry_bar = bar_curr
        ref_bar = bar_prev2
    elif tainted_sell:
        signal = "SELL"
        sub_pattern = "S20.2"
        entry_bar = bar_curr
        ref_bar = bar_prev2

    if not signal:
        return res

    # Check for S20.3, S20.4, S20.5 enhancements
    # If a classic or tainted pattern forms, we check if it aligns with HTF or FVG
    
    # 1. Check Sideway Trap (S20.5)
    if _is_sideway_trap(rates, signal):
        sub_pattern = "S20.5"
        
    # 2. Check FVG Bounce (S20.4)
    fvg_zone = _get_recent_fvg(rates, signal)
    if fvg_zone:
        # FVG Zone (Top, Bot)
        # If the entry_bar low/high touched the FVG, it's a bounce
        if signal == "BUY" and entry_bar['low'] <= fvg_zone[0] and entry_bar['low'] >= fvg_zone[1]:
            sub_pattern = "S20.4"
        elif signal == "SELL" and entry_bar['high'] >= fvg_zone[1] and entry_bar['high'] <= fvg_zone[0]:
            sub_pattern = "S20.4"

    # 3. Check HTF Alignment (S20.3)
    # If we have H1 swing data
    h1_swing = hhll_swing.get_swing_hl_pts("H1")
    if h1_swing and h1_swing[0] is not None and h1_swing[1] is not None:
        htf_high, htf_low = h1_swing[0], h1_swing[1]
        fibo_range = htf_high - htf_low
        fibo_50 = htf_low + (fibo_range * 0.5)
        fibo_618 = htf_low + (fibo_range * 0.382) # 61.8 retracement from top is 38.2 from bot
        fibo_786 = htf_low + (fibo_range * 0.214) 
        
        # If entry is within 50%-78.6% of HTF Fibo
        if signal == "BUY":
            # Retracement down
            if fibo_786 <= entry_bar['low'] <= fibo_50:
                sub_pattern = "S20.3"
        else:
            # Retracement up
            fibo_618_up = htf_high - (fibo_range * 0.382)
            fibo_786_up = htf_high - (fibo_range * 0.214)
            if fibo_50 <= entry_bar['high'] <= fibo_786_up:
                sub_pattern = "S20.3"

    # Calculate Entry, SL, TP
    entry = (entry_bar['open'] + entry_bar['close']) / 2.0
    
    # Fibo for TP:
    # BUY: 0 = Low, 100 = High
    if signal == "BUY":
        sl_raw = min(ref_bar['low'], entry_bar['low'])
        high_pt = max(ref_bar['high'], entry_bar['high'])
        fibo_range = high_pt - sl_raw
        tp_raw = sl_raw + (fibo_range * getattr(config, 'S20_FIBO_TP_LEVEL', 1.618))
        sl_buffer = config.SL_BUFFER() * getattr(config, 'S20_SL_BUFFER', 1.0)
        sl = sl_raw - sl_buffer
    else:
        sl_raw = max(ref_bar['high'], entry_bar['high'])
        low_pt = min(ref_bar['low'], entry_bar['low'])
        fibo_range = sl_raw - low_pt
        tp_raw = sl_raw - (fibo_range * getattr(config, 'S20_FIBO_TP_LEVEL', 1.618))
        sl_buffer = config.SL_BUFFER() * getattr(config, 'S20_SL_BUFFER', 1.0)
        sl = sl_raw + sl_buffer

    # Formatting reason based on sub_pattern
    reason_map = {
        "S20.1": "Classic Allin4s",
        "S20.2": "Tainted Allin4s (ตำหนิ)",
        "S20.3": "HTF Fibo Align Allin4s",
        "S20.4": "FVG Bounce Allin4s",
        "S20.5": "Sideway Trap Allin4s"
    }

    return {
        "signal": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp_raw,
        "reason": f"{sub_pattern} {reason_map[sub_pattern]}",
        "pattern": sub_pattern,
        "sid": 20
    }
