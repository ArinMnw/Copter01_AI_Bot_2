import pandas as pd
import numpy as np
import re
import config
from mt5_utils import now_bkk
import strategy20_13_23

def get_fuel_multiplier(current_tf, target_tf):
    return strategy20_13_23.get_fuel_multiplier(current_tf, target_tf)

def compute_indicators_df(rates):
    return strategy20_13_23.compute_indicators_df(rates)

def evaluate_bar(df, i, tf="H1"):
    # Step 1: Get baseline evaluation from v23
    res = strategy20_13_23.evaluate_bar(df, i, tf=tf)
    if res and res.get("signal") in ["BUY", "SELL"]:
        # Update pattern tag to v24
        res["pattern"] = res["pattern"].replace("S20.13.23", "S20.13.24")
        return res

    # Step 2: Check if blocked by v23 and evaluate V24 Zero-Loss Surgical Unlocks
    reason = res.get("reason", "") if res else ""
    clean_reason = re.sub(r'\(.*?\)', '', reason).strip()
    
    current_bar = df.iloc[i]
    prev_bar = df.iloc[i - 1]
    lookback_bars = df.iloc[max(0, i - 14) : max(0, i - 3)]
    if len(lookback_bars) == 0:
        return res
        
    # Guard: Must have strong range (>= 0.8 * ATR) to be unlocked by V24
    cur_range = current_bar['high'] - current_bar['low']
    if pd.isna(current_bar['atr']) or cur_range < (0.8 * current_bar['atr']):
        return res
        
    # Guard: Must pass Session Time Liquidity Traps before unlocking
    hour = current_bar['time_dt'].hour
    is_ny_pre_open = (hour in [12, 13])
    is_sydney_open = (hour in [23, 0])
    is_tokyo_buy = (hour == 2)
    is_late_ny_buy = (hour == 19)
    is_midnight_buy = (hour == 17)
    is_london_open = (hour == 8)
    is_london_fake = (hour == 9)
    
    local_low = lookback_bars['low'].min()
    local_high = lookback_bars['high'].max()
    active_mode = getattr(config, "S20_13_ACTIVE_MODE", 2.6)
    target_tf_buy = getattr(config, "S20_13_TARGET_TF_BUY", "H12")
    target_tf_sell = getattr(config, "S20_13_TARGET_TF_SELL", "D1")
    
    recent_3 = df.iloc[max(0, i-2):i+1]
    
    # Guard: Must satisfy Price Action Sweep & Engulfing structure
    sweep_buy = recent_3['low'].min() < local_low
    engulf_buy = current_bar['close'] > prev_bar['high']
    instant_sweep_buy = current_bar['low'] < local_low and current_bar['close'] > prev_bar['high']
    is_valid_buy_pa = (sweep_buy and engulf_buy) or instant_sweep_buy
    
    sweep_sell = recent_3['high'].max() > local_high
    engulf_sell = current_bar['close'] < prev_bar['low']
    instant_sweep_sell = current_bar['high'] > local_high and current_bar['close'] < prev_bar['low']
    is_valid_sell_pa = (sweep_sell and engulf_sell) or instant_sweep_sell
    
    unlock_sig = None
    if clean_reason == "BUY Low Volatility Drift Block":
        if current_bar['di_diff'] >= 5.0 and current_bar['vol_ratio'] >= 1.0 and current_bar['z_score'] >= 1.0 and current_bar['adx'] >= 15.0:
            unlock_sig = "BUY"
    elif clean_reason == "BUY Trend/Z Block":
        if current_bar['di_diff'] >= 0.0 and current_bar['adx'] <= 50.0 and current_bar['vol_ratio'] >= 1.5 and current_bar['z_score'] >= 0.0:
            unlock_sig = "BUY"
    elif clean_reason == "BUY Trend Exhaustion Block":
        if current_bar['adx'] > 50.0 and current_bar['vol_ratio'] > 1.2 and current_bar['z_score'] < -0.1:
            unlock_sig = "BUY"
    elif clean_reason == "SELL Oversold Trap Block":
        if current_bar['vol_ratio'] >= 1.2 and current_bar['rsi'] <= 35.0:
            unlock_sig = "SELL"
    elif clean_reason == "SELL Low ADX Above EMA50 Block":
        if current_bar['vol_ratio'] >= 2.0 and current_bar['adx'] <= 10.0:
            unlock_sig = "SELL"
    elif clean_reason == "SELL Low Volume Chop Block":
        if current_bar['hour'] == 5 and current_bar['vol_ratio'] >= 0.8:
            unlock_sig = "SELL"
            
    if unlock_sig == "BUY":
        if not is_valid_buy_pa or is_ny_pre_open or is_sydney_open or is_tokyo_buy or is_late_ny_buy or is_midnight_buy or is_london_open or is_london_fake:
            return res
        entry_price = current_bar['close']
        sweep_bottom = min(recent_3['low'].min(), current_bar['low'])
        sl = sweep_bottom - config.SL_BUFFER(current_bar['atr'])
        fuel = current_bar['atr'] * active_mode * get_fuel_multiplier(tf, target_tf_buy)
        tp = sweep_bottom + fuel
        return {
            "signal": "BUY",
            "entry": entry_price,
            "sl": sl,
            "tp": tp,
            "pattern": "S20.13.24 PA Confirmed BUY",
            "reason": f"V24 Zero-Loss Unlock ({clean_reason}) | TP {tp:.2f}"
        }
    elif unlock_sig == "SELL":
        if not is_valid_sell_pa or is_ny_pre_open or is_sydney_open or is_london_open or is_london_fake:
            return res
        entry_price = current_bar['close']
        sweep_top = max(recent_3['high'].max(), current_bar['high'])
        sl = sweep_top + config.SL_BUFFER(current_bar['atr'])
        fuel = current_bar['atr'] * active_mode * get_fuel_multiplier(tf, target_tf_sell)
        tp = sweep_top - fuel
        return {
            "signal": "SELL",
            "entry": entry_price,
            "sl": sl,
            "tp": tp,
            "pattern": "S20.13.24 PA Confirmed SELL",
            "reason": f"V24 Zero-Loss Unlock ({clean_reason}) | TP {tp:.2f}"
        }
        
    return res

def strategy_20_13_24(rates, tf="H1"):
    if rates is None or len(rates) < 20:
        return {"signal": "WAIT", "reason": "Not enough data"}
    df = compute_indicators_df(rates)
    return evaluate_bar(df, len(df) - 1, tf=tf)
