import mt5_worker as mt5
from config import engulf_min_price

_htf_fvg_cache = {}
_htf_fvg_last_fetch = {}

def clear_cache():
    _htf_fvg_cache.clear()
    _htf_fvg_last_fetch.clear()

def fetch_active_fvgs(tf_name: str, symbol: str, lookback: int = 2000, current_bar_time: int = None) -> bool:
    """Fetch history and build timeline of FVGs."""
    from config import TF_OPTIONS
    tf_val = TF_OPTIONS.get(tf_name)
    if tf_val is None:
        return False

    import time
    now_ts = int(time.time())
    
    # Check cache expiration (5 minutes)
    if current_bar_time is None:
        last_fetch = _htf_fvg_last_fetch.get(tf_name, 0)
        if now_ts - last_fetch < 300:
            return True
    else:
        if tf_name in _htf_fvg_cache:
            if _htf_fvg_last_fetch.get(f"{tf_name}_bar") == current_bar_time:
                return True

    rates = mt5.copy_rates_from_pos(symbol, tf_val, 0, lookback)
    if rates is None or len(rates) < 5:
        return False

    engulf_gap = engulf_min_price()
    all_fvgs = []
    
    # We will simulate bar by bar
    for i in range(2, len(rates)):
        c0 = rates[i]
        c1 = rates[i-1]
        c2 = rates[i-2]

        bull1 = c1["close"] > c1["open"]
        bear1 = c1["close"] < c1["open"]
        t0 = int(c0["time"])
        t1 = int(c1["time"])

        # Mitigate existing FVGs
        for fvg in all_fvgs:
            if fvg["end_time"] is None:
                if fvg["side"] == "BUY" and c0["close"] < fvg["bot"]:
                    fvg["end_time"] = t0
                elif fvg["side"] == "SELL" and c0["close"] > fvg["top"]:
                    fvg["end_time"] = t0

        # Check for new BUY FVG
        if bull1 and c1["close"] > c2["high"] + engulf_gap:
            if c0["low"] > c2["high"] + engulf_gap:
                all_fvgs.append({
                    "side": "BUY",
                    "bot": c2["high"],
                    "top": c0["low"],
                    "start_time": t1,
                    "end_time": None
                })

        # Check for new SELL FVG
        if bear1 and c1["close"] < c2["low"] - engulf_gap:
            if c0["high"] < c2["low"] - engulf_gap:
                all_fvgs.append({
                    "side": "SELL",
                    "bot": c0["high"],
                    "top": c2["low"],
                    "start_time": t1,
                    "end_time": None
                })

    _htf_fvg_cache[tf_name] = all_fvgs
    _htf_fvg_last_fetch[tf_name] = now_ts
    if current_bar_time is not None:
        _htf_fvg_last_fetch[f"{tf_name}_bar"] = current_bar_time
    
    return True

def is_price_in_htf_fvg(price: float, side: str, tf_names: list, at_time: int = None) -> bool:
    """Check if the price is inside any of the 3 MOST RECENT active FVGs at `at_time`."""
    import time
    if at_time is None:
        at_time = int(time.time())
        
    for tf in tf_names:
        # Auto fetch if empty or expired
        from config import SYMBOL
        fetch_active_fvgs(tf, SYMBOL, lookback=2000)
        
        fvgs = _htf_fvg_cache.get(tf, [])
        
        # Find all FVGs that are active at `at_time`
        active_fvgs = []
        for fvg in fvgs:
            if fvg["side"] == side:
                if fvg["start_time"] <= at_time:
                    if fvg["end_time"] is None or at_time < fvg["end_time"]:
                        active_fvgs.append(fvg)
        
        # Sort by start_time descending to get the most recent ones
        active_fvgs.sort(key=lambda x: x["start_time"], reverse=True)
        
        # Only consider the 3 most recent FVGs (FVG 1, 2, 3)
        recent_fvgs = active_fvgs[:3]
        
        for fvg in recent_fvgs:
            if fvg["bot"] <= price <= fvg["top"]:
                return True
                
    return False
