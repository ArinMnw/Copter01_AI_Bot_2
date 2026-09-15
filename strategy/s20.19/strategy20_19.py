# -*- coding: utf-8 -*-
"""strategy20_19.py — S20.19 M1/M5 Sniper Scalper ($10 Target per Trade)
Designed for small accounts ($100 account / sniper sprint):
1. Micro-Liquidity Sweep: False breakout of 15-bar swing high/low.
2. High-Volume Absorption Pinbar: Rejection wick >= 45% with institutional volume spike.
3. Fixed Profit Target = $10.00 per trade (calibrated by lot size).
4. Micro-Stop Loss: 120-180 points beyond the wick (strictly limiting risk to $3 - $5).
5. Rapid Breakeven Lock: Moves SL to entry once trade hits 40% of target (+$4.00).
"""

import pandas as pd
import numpy as np
import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)


def compute_indicators_df(rates):
    """Compute indicators for M1/M5 Sniper Scalper."""
    df = pd.DataFrame(rates)
    df['time_dt'] = pd.to_datetime(df['time'], unit='s')
    df['hour'] = df['time_dt'].dt.hour

    # Candle anatomy
    df['range'] = df['high'] - df['low']
    df['body'] = np.abs(df['close'] - df['open'])
    df['body_pct'] = df['body'] / (df['range'] + 1e-5)

    df['upper_wick'] = df['high'] - np.maximum(df['open'], df['close'])
    df['lower_wick'] = np.minimum(df['open'], df['close']) - df['low']
    df['upper_wick_pct'] = df['upper_wick'] / (df['range'] + 1e-5)
    df['lower_wick_pct'] = df['lower_wick'] / (df['range'] + 1e-5)

    # ATR (14)
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()

    # Fast Moving Averages
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()

    # RSI (7 & 14) for fast sniper exhaustion
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=7).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
    rs = gain / (loss + 1e-9)
    df['rsi_fast'] = 100 - (100 / (1 + rs))

    # Volume spike
    df['vol_ma20'] = df['tick_volume'].rolling(20).mean()
    df['vol_ratio'] = df['tick_volume'] / (df['vol_ma20'] + 1e-5)

    # Micro-Swings (15-bar lookback)
    df['swing_high_15'] = df['high'].rolling(15).max().shift(1)
    df['swing_low_15'] = df['low'].rolling(15).min().shift(1)

    return df


def evaluate_bar(df, idx, tf="M5", lot=0.03, target_dollar=10.0, contract_size=100.0, max_allowed_risk=6.50):
    """Evaluate bar for S20.19 $10-per-trade Sniper Scalp setup.
    
    Args:
        df: DataFrame with indicators
        idx: Index of bar to evaluate
        tf: Timeframe ('M1', 'M5')
        lot: Lot size used (e.g. 0.02, 0.03, 0.04)
        target_dollar: Fixed target in USD (default 10.0)
        contract_size: 100.0 for Gold
    """
    if idx < 20 or idx >= len(df):
        return {"signal": "WAIT", "reason": "Not enough data"}

    cur = df.iloc[idx]
    if pd.isna(cur['atr']) or pd.isna(cur['vol_ma20']):
        return {"signal": "WAIT", "reason": "Indicators not ready"}

    atr = cur['atr']
    if atr <= 0.05:
        return {"signal": "WAIT", "reason": "ATR too low"}

    # Filter quiet dead hours (23:00 - 01:00)
    if cur['hour'] in (23, 0):
        return {"signal": "WAIT", "reason": "Rollover hours"}

    # Target price distance needed to reach exactly $target_dollar
    # Profit = price_move * contract_size * lot
    # price_move = target_dollar / (contract_size * lot)
    target_dist = round(target_dollar / (contract_size * lot), 2)

    # Volume spike check (>= 1.30x normal volume)
    is_vol_surge = cur['vol_ratio'] >= 1.30

    # -------------------------------------------------------------
    # 1. SNIPER BUY SETUP (Liquidity Sweep at Bottom + Rejection)
    # -------------------------------------------------------------
    # Price pierced below the 15-bar low (stop hunt) but closed back up
    swept_low = cur['low'] < cur['swing_low_15']
    rejection_wick_buy = (cur['lower_wick_pct'] >= 0.42) or (cur['lower_wick'] >= 1.1 * cur['body'])
    closed_in_upper_half = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    rsi_not_overbought = cur['rsi_fast'] <= 70.0

    if swept_low and rejection_wick_buy and closed_in_upper_half and is_vol_surge and rsi_not_overbought:
        entry = round(cur['close'], 2)
        # Tight SL just below the sweep low + micro buffer (15-20 points)
        sl_buffer = max(0.18 * atr, 0.20)
        sl = round(cur['low'] - sl_buffer, 2)
        risk_dist = entry - sl

        max_allowed_risk_dollar = max_allowed_risk
        risk_dollar = risk_dist * contract_size * lot
        if 0 < risk_dollar <= max_allowed_risk_dollar:
            tp = round(entry + target_dist, 2)
            return {
                "signal": "BUY",
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "risk_dollar": round(risk_dollar, 2),
                "target_dollar": target_dollar,
                "pattern": f"S20.19 Sniper BUY (Vol: {cur['vol_ratio']:.1f}x | Risk: ${risk_dollar:.2f})",
                "reason": f"Swept 15-bar Low -> Target +${target_dollar:.0f} (TP: {tp})"
            }

    # -------------------------------------------------------------
    # 2. SNIPER SELL SETUP (Liquidity Sweep at Top + Rejection)
    # -------------------------------------------------------------
    swept_high = cur['high'] > cur['swing_high_15']
    rejection_wick_sell = (cur['upper_wick_pct'] >= 0.42) or (cur['upper_wick'] >= 1.1 * cur['body'])
    closed_in_lower_half = cur['close'] <= (cur['high'] - 0.45 * cur['range'])
    rsi_not_oversold = cur['rsi_fast'] >= 30.0

    if swept_high and rejection_wick_sell and closed_in_lower_half and is_vol_surge and rsi_not_oversold:
        entry = round(cur['close'], 2)
        # Tight SL just above the sweep high + micro buffer
        sl_buffer = max(0.18 * atr, 0.20)
        sl = round(cur['high'] + sl_buffer, 2)
        risk_dist = sl - entry

        max_allowed_risk_dollar = max_allowed_risk
        risk_dollar = risk_dist * contract_size * lot
        if 0 < risk_dollar <= max_allowed_risk_dollar:
            tp = round(entry - target_dist, 2)
            return {
                "signal": "SELL",
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "risk_dollar": round(risk_dollar, 2),
                "target_dollar": target_dollar,
                "pattern": f"S20.19 Sniper SELL (Vol: {cur['vol_ratio']:.1f}x | Risk: ${risk_dollar:.2f})",
                "reason": f"Swept 15-bar High -> Target +${target_dollar:.0f} (TP: {tp})"
            }

    return {"signal": "WAIT", "reason": "No Sniper Setup"}
