# -*- coding: utf-8 -*-
"""strategy20_18.py — S20.18 Institutional Order Flow Delta & Passive Absorption
Strategy based on Institutional Microstructure & Order Flow:
1. Footprint / Delta Proxy via tick_volume & bar price distribution.
2. Passive Absorption: Aggressive market orders absorbed by institutional iceberg/passive limit orders.
3. Liquidity Hunt: Sweeping recent swing highs/lows with high volume but failing to sustain price progress.
4. Delta Exhaustion & Reversal Confirmation.
"""

import pandas as pd
import numpy as np
import os
import sys

# Ensure parent path is in sys.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

try:
    import config
    import tpsl_engine
except Exception:
    config = None
    tpsl_engine = None


def compute_indicators_df(rates):
    """Compute indicator dataframe with Footprint Delta and Absorption metrics."""
    df = pd.DataFrame(rates)
    df['time_dt'] = pd.to_datetime(df['time'], unit='s')
    df['hour'] = df['time_dt'].dt.hour

    # Basic price anatomy
    df['range'] = df['high'] - df['low']
    df['body'] = np.abs(df['close'] - df['open'])
    df['body_pct'] = df['body'] / (df['range'] + 1e-5)

    df['upper_wick'] = df['high'] - np.maximum(df['open'], df['close'])
    df['lower_wick'] = np.minimum(df['open'], df['close']) - df['low']
    df['upper_wick_pct'] = df['upper_wick'] / (df['range'] + 1e-5)
    df['lower_wick_pct'] = df['lower_wick'] / (df['range'] + 1e-5)

    # ATR calculation (14 period)
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()

    # Trend moving averages
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

    # RSI (14)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))

    # Volume & Order Flow Delta Proxy
    # Approximate intra-bar delta using price location relative to range
    # intra_force: -1 (all selling down to low) to +1 (all buying up to high)
    intra_force = (2.0 * (df['close'] - df['low']) / (df['range'] + 1e-5)) - 1.0
    df['delta'] = df['tick_volume'] * intra_force
    df['cvd'] = df['delta'].cumsum()

    # Volume averages & spike detection
    df['vol_ma20'] = df['tick_volume'].rolling(20).mean()
    df['vol_ratio'] = df['tick_volume'] / (df['vol_ma20'] + 1e-5)

    # Recent Swing Extremes (lookback 10 bars)
    df['swing_high_10'] = df['high'].rolling(10).max().shift(1)
    df['swing_low_10'] = df['low'].rolling(10).min().shift(1)

    return df


def evaluate_bar(df, idx, tf="H1", entry_mode="MARKET", rr_ratio=1.8):
    """Evaluate if current bar exhibits Institutional Passive Absorption.
    
    Args:
        df: DataFrame with precomputed indicators
        idx: Index of the bar to evaluate
        tf: Timeframe string (e.g. 'M5', 'M15', 'H1')
        entry_mode: 'MARKET' (at close) or 'RETEST' (at 50% wick)
        rr_ratio: Risk-reward ratio for fixed TP (default 1.8)
        
    Returns:
        dict with signal details or WAIT
    """
    if idx < 25 or idx >= len(df):
        return {"signal": "WAIT", "reason": "Not enough data"}

    cur = df.iloc[idx]
    prev = df.iloc[idx - 1]

    # Required indicators check
    if pd.isna(cur['atr']) or pd.isna(cur['vol_ma20']) or pd.isna(cur['rsi']):
        return {"signal": "WAIT", "reason": "Indicators not ready"}

    atr = cur['atr']
    if atr <= 0.05:
        return {"signal": "WAIT", "reason": "ATR too low"}

    # Volatility Filter: Bar range must be meaningful (not dead quiet/spread noise)
    if cur['range'] < 0.45 * atr:
        return {"signal": "WAIT", "reason": "Range too small"}

    # Time trap / Low liquidity rollover filter (23:00 - 00:59)
    if cur['hour'] in (23, 0):
        return {"signal": "WAIT", "reason": "Rollover hour"}

    vol_ratio = cur['vol_ratio']
    # Institutional Volume Surge Threshold
    is_high_volume = vol_ratio >= 1.25

    # -------------------------------------------------------------------------
    # 1. BULLISH PASSIVE ABSORPTION (BUY)
    # -------------------------------------------------------------------------
    # Condition A: Liquidity sweep / Test of swing low
    swept_low = (cur['low'] <= cur['swing_low_10']) or (cur['low'] <= df.iloc[idx-5:idx]['low'].min())
    
    # Condition B: Strong Lower Wick Rejection (Absorption footprint)
    # Sellers pushed price down aggressively, but institutional limits absorbed it
    has_absorption_wick_buy = (cur['lower_wick_pct'] >= 0.38) or (cur['lower_wick'] >= 1.1 * cur['body'])
    
    # Condition C: Price closed off the lows (Buyers reclaimed control)
    closed_high_in_bar = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    
    # Condition D: RSI not overbought
    rsi_ok_buy = cur['rsi'] <= 68.0

    if swept_low and is_high_volume and has_absorption_wick_buy and closed_high_in_bar and rsi_ok_buy:
        # Buffer below the absorption wick low
        sl_buffer = max(0.20 * atr, 0.25)
        sl = round(cur['low'] - sl_buffer, 2)
        
        if entry_mode == "RETEST":
            # Enter at 50% retracement of the absorption wick
            entry = round(cur['low'] + (0.5 * cur['lower_wick']), 2)
        else:
            # Enter at bar close
            entry = round(cur['close'], 2)

        risk = entry - sl
        if risk <= 0:
            return {"signal": "WAIT", "reason": "Invalid risk calculation"}

        # TP calculation (Risk:Reward 1.8R or TPSL Engine)
        tp = round(entry + (risk * rr_ratio), 2)

        return {
            "signal": "BUY",
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "risk": risk,
            "pattern": f"S20.18 Bullish Absorption (Vol: {vol_ratio:.1f}x | Wick: {cur['lower_wick_pct']*100:.0f}%)",
            "order_mode": "limit" if entry_mode == "RETEST" else "market",
            "reason": f"Swept Low {cur['swing_low_10']:.2f} with High Vol Absorption"
        }

    # -------------------------------------------------------------------------
    # 2. BEARISH PASSIVE ABSORPTION (SELL)
    # -------------------------------------------------------------------------
    # Condition A: Liquidity sweep / Test of swing high
    swept_high = (cur['high'] >= cur['swing_high_10']) or (cur['high'] >= df.iloc[idx-5:idx]['high'].max())
    
    # Condition B: Strong Upper Wick Rejection (Absorption footprint)
    # Buyers pushed price up aggressively, but institutional limits absorbed it
    has_absorption_wick_sell = (cur['upper_wick_pct'] >= 0.38) or (cur['upper_wick'] >= 1.1 * cur['body'])
    
    # Condition C: Price closed off the highs (Sellers reclaimed control)
    closed_low_in_bar = cur['close'] <= (cur['high'] - 0.45 * cur['range'])
    
    # Condition D: RSI not oversold
    rsi_ok_sell = cur['rsi'] >= 32.0

    if swept_high and is_high_volume and has_absorption_wick_sell and closed_low_in_bar and rsi_ok_sell:
        # Buffer above the absorption wick high
        sl_buffer = max(0.20 * atr, 0.25)
        sl = round(cur['high'] + sl_buffer, 2)

        if entry_mode == "RETEST":
            # Enter at 50% retracement of the absorption wick
            entry = round(cur['high'] - (0.5 * cur['upper_wick']), 2)
        else:
            # Enter at bar close
            entry = round(cur['close'], 2)

        risk = sl - entry
        if risk <= 0:
            return {"signal": "WAIT", "reason": "Invalid risk calculation"}

        # TP calculation (Risk:Reward 1.8R or TPSL Engine)
        tp = round(entry - (risk * rr_ratio), 2)

        return {
            "signal": "SELL",
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "risk": risk,
            "pattern": f"S20.18 Bearish Absorption (Vol: {vol_ratio:.1f}x | Wick: {cur['upper_wick_pct']*100:.0f}%)",
            "order_mode": "limit" if entry_mode == "RETEST" else "market",
            "reason": f"Swept High {cur['swing_high_10']:.2f} with High Vol Absorption"
        }

    return {"signal": "WAIT", "reason": "No Absorption Setup"}
