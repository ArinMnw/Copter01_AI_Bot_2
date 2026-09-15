# -*- coding: utf-8 -*-
"""strategy20_31.py — S20.31 Verifiable Institutional Synergy (Zero-Lookahead M1-Execution):
Strict Requirements:
1. Strict 0.01 Lot single position (no partial lot splits).
2. True Multi-Strategy Confluence on the SAME bar.
3. ZERO Lookahead Bias — indicators strictly backward-looking.
4. ZERO "ชน SL แล้วชน TP" — executed on 352,000+ real 1-minute (M1) bars.
   If SL and TP occur in the same minute, SL ALWAYS takes precedence.
"""

import pandas as pd
import numpy as np
import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)


def compute_indicators_df(gold_rates, silver_rates=None):
    """Compute synchronized multi-strategy indicators on setup timeframe (M30 or M15).
    Every indicator is strictly causal (no lookahead, no future leakage).
    """
    df = pd.DataFrame(gold_rates)
    df['time_dt'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time_dt'].dt.date
    df['hour'] = df['time_dt'].dt.hour
    df['minute'] = df['time_dt'].dt.minute

    # Anatomy
    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3.0
    df['range'] = df['high'] - df['low']
    df['body'] = np.abs(df['close'] - df['open'])
    df['body_pct'] = df['body'] / (df['range'] + 1e-5)
    df['upper_wick'] = df['high'] - np.maximum(df['open'], df['close'])
    df['lower_wick'] = np.minimum(df['open'], df['close']) - df['low']
    df['upper_wick_pct'] = df['upper_wick'] / (df['range'] + 1e-5)
    df['lower_wick_pct'] = df['lower_wick'] / (df['range'] + 1e-5)

    # ATR (14) - strictly rolling
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift(1))
    low_close = np.abs(df['low'] - df['close'].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()

    # RSI (14) - strictly rolling
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-5)
    df['rsi'] = 100 - (100 / (1 + rs))

    # Volume metrics
    df['vol_ma20'] = df['tick_volume'].rolling(20).mean()
    df['vol_ratio'] = df['tick_volume'] / (df['vol_ma20'] + 1e-5)

    # Session Anchored VWAP (Daily Cumulative from 00:00 server time)
    df['pv'] = df['typical_price'] * df['tick_volume']
    df['cum_pv'] = df.groupby('date')['pv'].cumsum()
    df['cum_vol'] = df.groupby('date')['tick_volume'].cumsum()
    df['vwap'] = df['cum_pv'] / (df['cum_vol'] + 1e-5)

    df['dev_sq'] = df['tick_volume'] * ((df['typical_price'] - df['vwap']) ** 2)
    df['cum_dev_sq'] = df.groupby('date')['dev_sq'].cumsum()
    df['vwap_std'] = np.sqrt(df['cum_dev_sq'] / (df['cum_vol'] + 1e-5))
    df['vwap_upper_10'] = df['vwap'] + (1.0 * df['vwap_std'])
    df['vwap_lower_10'] = df['vwap'] - (1.0 * df['vwap_std'])
    df['vwap_upper_12'] = df['vwap'] + (1.2 * df['vwap_std'])
    df['vwap_lower_12'] = df['vwap'] - (1.2 * df['vwap_std'])

    # Swings (Shifted by 1 so current bar is NEVER in its own swing level!)
    df['swing_high_12'] = df['high'].rolling(12).max().shift(1)
    df['swing_low_12'] = df['low'].rolling(12).min().shift(1)

    # Asian Session Range (00:00 - 08:00 server time)
    asian_mask = (df['hour'] >= 0) & (df['hour'] < 8)
    df['asian_high_raw'] = np.where(asian_mask, df['high'], np.nan)
    df['asian_low_raw'] = np.where(asian_mask, df['low'], np.nan)
    day_asian_high = df.groupby('date')['asian_high_raw'].transform('max')
    day_asian_low = df.groupby('date')['asian_low_raw'].transform('min')
    df['asian_high'] = day_asian_high
    df['asian_low'] = day_asian_low

    # Previous Day High / Low (Shifted by 1 day so today only sees yesterday!)
    day_highs = df.groupby('date')['high'].max()
    day_lows = df.groupby('date')['low'].min()
    df['pdh'] = df['date'].map(day_highs.shift(1))
    df['pdl'] = df['date'].map(day_lows.shift(1))

    # Synchronize Silver (XAGUSD.iux)
    if silver_rates is not None:
        s_df = pd.DataFrame(silver_rates)
        s_df['s_swing_high_12'] = s_df['high'].rolling(12).max().shift(1)
        s_df['s_swing_low_12'] = s_df['low'].rolling(12).min().shift(1)
        df = pd.merge_asof(
            df,
            s_df[['time', 'high', 'low', 'close', 's_swing_high_12', 's_swing_low_12']],
            on='time',
            suffixes=('', '_silver')
        )

    return df


def evaluate_setup(df, idx, synergy_mode="sweep_smt_vwap", min_vol=1.30, min_wick=0.38):
    """Evaluate if bar idx triggers a high-probability institutional setup."""
    if idx < 45 or idx >= len(df):
        return None

    cur = df.iloc[idx]
    atr = cur['atr']
    if pd.isna(atr) or atr <= 0.05 or cur['range'] < 0.45 * atr:
        return None

    # London & NY Active Trading Hours (08:00 - 18:00 server time)
    if not (8 <= cur['hour'] <= 18):
        return None

    # Volume Climax
    if cur['vol_ratio'] < min_vol:
        return None

    # Liquidity Pool Sweeps (Swing 12, Asian H/L, PDH/PDL)
    swing_high = cur['swing_high_12']
    swing_low = cur['swing_low_12']
    asian_high = cur['asian_high']
    asian_low = cur['asian_low']
    pdh = cur['pdh']
    pdl = cur['pdl']

    swept_high = (cur['high'] >= swing_high) or \
                 (not pd.isna(asian_high) and cur['high'] >= asian_high) or \
                 (not pd.isna(pdh) and cur['high'] >= pdh)

    swept_low = (cur['low'] <= swing_low) or \
                (not pd.isna(asian_low) and cur['low'] <= asian_low) or \
                (not pd.isna(pdl) and cur['low'] <= pdl)

    # SMT Divergence
    has_silver = 'high_silver' in df.columns and not pd.isna(cur.get('high_silver', np.nan))
    smt_bearish = False
    smt_bullish = False

    if has_silver:
        s_high = cur['high_silver']
        s_low = cur['low_silver']
        s_swing_high = cur['s_swing_high_12']
        s_swing_low = cur['s_swing_low_12']

        if (cur['high'] >= swing_high) and (s_high < s_swing_high):
            smt_bearish = True
        elif (cur['high'] < swing_high) and (s_high >= s_swing_high):
            smt_bearish = True

        if (cur['low'] <= swing_low) and (s_low > s_swing_low):
            smt_bullish = True
        elif (cur['low'] > swing_low) and (s_low <= s_swing_low):
            smt_bullish = True

    # VWAP Discount/Premium
    in_discount = True
    in_premium = True
    if not pd.isna(cur['vwap_std']) and cur['vwap_std'] >= 0.7:
        in_discount = cur['low'] <= cur['vwap_lower_10']
        in_premium = cur['high'] >= cur['vwap_upper_10']

    # Anatomy Confirmations
    has_wick_buy = (cur['lower_wick_pct'] >= min_wick) or (cur['lower_wick'] >= 1.1 * cur['body'])
    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    rsi_ok_buy = cur['rsi'] <= 68.0

    has_wick_sell = (cur['upper_wick_pct'] >= min_wick) or (cur['upper_wick'] >= 1.1 * cur['body'])
    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])
    rsi_ok_sell = cur['rsi'] >= 32.0

    sig = None

    if has_wick_buy and closed_high and rsi_ok_buy and swept_low:
        if synergy_mode == "sweep_only":
            sig = "BUY"
        elif synergy_mode == "sweep_smt":
            if smt_bullish:
                sig = "BUY"
        elif synergy_mode == "sweep_smt_vwap":
            # Confluence: Sweep + SMT + VWAP Discount
            if smt_bullish and in_discount:
                sig = "BUY"

    if sig is None and has_wick_sell and closed_low and rsi_ok_sell and swept_high:
        if synergy_mode == "sweep_only":
            sig = "SELL"
        elif synergy_mode == "sweep_smt":
            if smt_bearish:
                sig = "SELL"
        elif synergy_mode == "sweep_smt_vwap":
            if smt_bearish and in_premium:
                sig = "SELL"

    if not sig:
        return None

    # Entry: Fibo 38.2% of wick
    sl_buf = max(0.20 * atr, 0.25)
    retest_depth = 0.382

    if sig == "BUY":
        sl = round(cur['low'] - sl_buf, 2)
        entry = round(cur['low'] + (retest_depth * cur['lower_wick']), 2)
        risk = entry - sl
        if risk <= 0:
            return None
    else:
        sl = round(cur['high'] + sl_buf, 2)
        entry = round(cur['high'] - (retest_depth * cur['upper_wick']), 2)
        risk = sl - entry
        if risk <= 0:
            return None

    return {
        "time": int(cur['time']),
        "time_str": str(cur['time_dt']),
        "signal": sig,
        "entry": entry,
        "sl": sl,
        "risk": risk,
        "atr": atr
    }
