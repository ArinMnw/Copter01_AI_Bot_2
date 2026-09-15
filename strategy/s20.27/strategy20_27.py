# -*- coding: utf-8 -*-
"""strategy20_27.py — S20.27 Omni-Institutional Nexus Engine:
The Ultimate Synergistic Multi-Strategy Fusion:
1. Engine 1: Session Liquidity Pool Sweep (Asian Range H/L, PDH/PDL, Swing 12)
2. Engine 2: Intermarket SMT Divergence (Gold XAUUSD vs Silver XAGUSD)
3. Engine 3: ICT Fair Value Gap (FVG) Imbalance & Displacement Confirmation
4. Engine 4: Session Anchored VWAP Statistical Extremes (Outside ±1.0σ)
5. Engine 5: Multi-Timeframe Fractal Trend Guard (HTF Bias Protection)
6. Precision Execution: Fibo 38.2% / FVG Retest + Dynamic Regime Dual-Exit (1.8R Scalp + 4.5R Dynamic Runner)
"""

import pandas as pd
import numpy as np
import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)


def compute_indicators_df(gold_rates, silver_rates=None, h1_rates=None):
    """Compute synchronized indicators for S20.27 Omni-Institutional Nexus."""
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

    # ATR (14)
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()

    # RSI (14)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-5)
    df['rsi'] = 100 - (100 / (1 + rs))

    # Trend moving averages
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

    # Volume metrics
    df['vol_ma20'] = df['tick_volume'].rolling(20).mean()
    df['vol_ratio'] = df['tick_volume'] / (df['vol_ma20'] + 1e-5)

    # Daily Anchored VWAP & Standard Deviation Bands
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

    # Local Swings (lookback 12)
    df['swing_high_12'] = df['high'].rolling(12).max().shift(1)
    df['swing_low_12'] = df['low'].rolling(12).min().shift(1)
    df['opposite_high_40'] = df['high'].rolling(40).max().shift(1)
    df['opposite_low_40'] = df['low'].rolling(40).min().shift(1)

    # ICT Fair Value Gap (FVG) Imbalance Detection (3-bar pattern)
    # Bullish FVG: Low of bar i > High of bar i-2
    # Bearish FVG: High of bar i < Low of bar i-2
    df['fvg_bull_top'] = df['low']
    df['fvg_bull_bot'] = df['high'].shift(2)
    df['has_fvg_bull'] = (df['fvg_bull_top'] > df['fvg_bull_bot']) & (df['close'] > df['open'])

    df['fvg_bear_top'] = df['low'].shift(2)
    df['fvg_bear_bot'] = df['high']
    df['has_fvg_bear'] = (df['fvg_bear_top'] > df['fvg_bear_bot']) & (df['close'] < df['open'])

    # Asian Session Range (00:00 - 08:00 server time)
    asian_mask = (df['hour'] >= 0) & (df['hour'] < 8)
    df['asian_high_raw'] = np.where(asian_mask, df['high'], np.nan)
    df['asian_low_raw'] = np.where(asian_mask, df['low'], np.nan)
    day_asian_high = df.groupby('date')['asian_high_raw'].transform('max')
    day_asian_low = df.groupby('date')['asian_low_raw'].transform('min')
    df['asian_high'] = day_asian_high
    df['asian_low'] = day_asian_low

    # Previous Day High & Low (PDH / PDL)
    day_highs = df.groupby('date')['high'].max()
    day_lows = df.groupby('date')['low'].min()
    df['pdh'] = df['date'].map(day_highs.shift(1))
    df['pdl'] = df['date'].map(day_lows.shift(1))

    # Synchronize Silver (XAGUSD.iux) if provided
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

    # Synchronize H1 HTF trend if provided
    if h1_rates is not None:
        h_df = pd.DataFrame(h1_rates)
        h_df['h1_ema50'] = h_df['close'].ewm(span=50, adjust=False).mean()
        h_df['h1_ema200'] = h_df['close'].ewm(span=200, adjust=False).mean()
        h_df['h1_trend'] = np.where(h_df['close'] > h_df['h1_ema50'], 1, -1)
        df = pd.merge_asof(
            df,
            h_df[['time', 'h1_ema50', 'h1_ema200', 'h1_trend']],
            on='time',
            suffixes=('', '_h1')
        )

    return df


def evaluate_s20_27_bar(
    df,
    idx,
    tf="M30",
    mode="nexus_ultimate",
    min_vol=1.30,
    min_wick=0.38,
    retest_depth=0.382
):
    """Evaluate bar for S20.27 Omni-Institutional Nexus.
    Modes:
    1. 'benchmark_s26': Standard S20.26 Quad Apex (Benchmark)
    2. 'nexus_fvg': S20.26 + FVG Imbalance Displacement Confirmation
    3. 'nexus_htf': S20.26 + H1 Multi-Timeframe Trend Guard
    4. 'nexus_ultimate': Complete Omni-Nexus (Session Pool + SMT + VWAP + FVG + Dynamic Regime Runner)
    """
    if idx < 45 or idx >= len(df):
        return None

    cur = df.iloc[idx]
    atr = cur['atr']
    if pd.isna(atr) or atr <= 0.05 or cur['range'] < 0.45 * atr:
        return None

    # Active Session Window (London & NY Killzones 08:00 - 18:00 server / 14:00 - 00:00 BKK)
    if not (8 <= cur['hour'] <= 18):
        return None

    # Volume Climax
    if cur['vol_ratio'] < min_vol:
        return None

    # VWAP Discount/Premium
    in_discount = True
    in_premium = True
    if not pd.isna(cur['vwap_std']) and cur['vwap_std'] >= 0.7:
        in_discount = cur['low'] <= cur['vwap_lower_10']
        in_premium = cur['high'] >= cur['vwap_upper_10']

    # Liquidity Pool Anchors
    swing_high = cur['swing_high_12']
    swing_low = cur['swing_low_12']
    asian_high = cur['asian_high']
    asian_low = cur['asian_low']
    pdh = cur['pdh']
    pdl = cur['pdl']

    # Gold Sweeps
    gold_swept_high = cur['high'] >= swing_high
    gold_swept_low = cur['low'] <= swing_low

    session_swept_high = False
    session_swept_low = False
    if not pd.isna(asian_high) and cur['high'] >= asian_high:
        session_swept_high = True
    if not pd.isna(asian_low) and cur['low'] <= asian_low:
        session_swept_low = True
    if not pd.isna(pdh) and cur['high'] >= pdh:
        session_swept_high = True
    if not pd.isna(pdl) and cur['low'] <= pdl:
        session_swept_low = True

    # SMT Intermarket Divergence with Silver
    has_silver = 'high_silver' in df.columns and not pd.isna(cur.get('high_silver', np.nan))
    smt_bearish = False
    smt_bullish = False

    if has_silver:
        s_high = cur['high_silver']
        s_low = cur['low_silver']
        s_swing_high = cur['s_swing_high_12']
        s_swing_low = cur['s_swing_low_12']

        if gold_swept_high and (s_high < s_swing_high):
            smt_bearish = True
        elif (not gold_swept_high) and (s_high >= s_swing_high and cur['high'] < swing_high):
            smt_bearish = True

        if gold_swept_low and (s_low > s_swing_low):
            smt_bullish = True
        elif (not gold_swept_low) and (s_low <= s_swing_low and cur['low'] > swing_low):
            smt_bullish = True

    # ICT Fair Value Gap Confirmation (Check recent 3 bars for FVG imbalance)
    has_recent_fvg_bull = False
    has_recent_fvg_bear = False
    for k in range(max(0, idx - 2), idx + 1):
        if df.iloc[k].get('has_fvg_bull', False):
            has_recent_fvg_bull = True
        if df.iloc[k].get('has_fvg_bear', False):
            has_recent_fvg_bear = True

    # HTF Trend Guard (H1 Trend)
    h1_bullish = True
    h1_bearish = True
    if 'h1_trend' in df.columns and not pd.isna(cur.get('h1_trend', np.nan)):
        h1_trend_val = cur['h1_trend']
        h1_bullish = (h1_trend_val >= 0) or (cur['low'] <= cur.get('vwap_lower_12', cur['vwap_lower_10']))
        h1_bearish = (h1_trend_val <= 0) or (cur['high'] >= cur.get('vwap_upper_12', cur['vwap_upper_10']))

    # Anatomy Confirmations
    has_wick_buy = (cur['lower_wick_pct'] >= min_wick) or (cur['lower_wick'] >= 1.1 * cur['body'])
    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    rsi_ok_buy = cur['rsi'] <= 68.0

    has_wick_sell = (cur['upper_wick_pct'] >= min_wick) or (cur['upper_wick'] >= 1.1 * cur['body'])
    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])
    rsi_ok_sell = cur['rsi'] >= 32.0

    sig = None
    reason = ""

    # -------------------------------------------------------------------------
    # 1. BULLISH (BUY) EVALUATION
    # -------------------------------------------------------------------------
    if has_wick_buy and closed_high and rsi_ok_buy:
        has_sweep = gold_swept_low or session_swept_low
        smt_or_deep = smt_bullish or (cur['low'] <= cur.get('vwap_lower_12', cur['vwap_lower_10']))

        if mode == 'benchmark_s26':
            if has_sweep and smt_or_deep and in_discount:
                sig = "BUY"
                reason = "S20.26 Benchmark Quad Apex"
        elif mode == 'nexus_fvg':
            # Must also have FVG imbalance or strong displacement body
            if has_sweep and smt_or_deep and in_discount and (has_recent_fvg_bull or cur['body_pct'] >= 0.35):
                sig = "BUY"
                reason = "Nexus + FVG Displacement Retest"
        elif mode == 'nexus_htf':
            if has_sweep and smt_or_deep and in_discount and h1_bullish:
                sig = "BUY"
                reason = "Nexus + H1 Trend Guard"
        elif mode == 'nexus_ultimate':
            # Complete Confluence: Sweep + SMT/Deep + VWAP Discount + HTF Alignment + Body/FVG
            fvg_or_displacement = has_recent_fvg_bull or (cur['body_pct'] >= 0.30)
            if has_sweep and smt_or_deep and in_discount and h1_bullish and fvg_or_displacement:
                sig = "BUY"
                reason = "Omni-Nexus Ultimate (Sweep+SMT+VWAP+H1+FVG)"

    # -------------------------------------------------------------------------
    # 2. BEARISH (SELL) EVALUATION
    # -------------------------------------------------------------------------
    if sig is None and has_wick_sell and closed_low and rsi_ok_sell:
        has_sweep = gold_swept_high or session_swept_high
        smt_or_deep = smt_bearish or (cur['high'] >= cur.get('vwap_upper_12', cur['vwap_upper_10']))

        if mode == 'benchmark_s26':
            if has_sweep and smt_or_deep and in_premium:
                sig = "SELL"
                reason = "S20.26 Benchmark Quad Apex"
        elif mode == 'nexus_fvg':
            if has_sweep and smt_or_deep and in_premium and (has_recent_fvg_bear or cur['body_pct'] >= 0.35):
                sig = "SELL"
                reason = "Nexus + FVG Displacement Retest"
        elif mode == 'nexus_htf':
            if has_sweep and smt_or_deep and in_premium and h1_bearish:
                sig = "SELL"
                reason = "Nexus + H1 Trend Guard"
        elif mode == 'nexus_ultimate':
            fvg_or_displacement = has_recent_fvg_bear or (cur['body_pct'] >= 0.30)
            if has_sweep and smt_or_deep and in_premium and h1_bearish and fvg_or_displacement:
                sig = "SELL"
                reason = "Omni-Nexus Ultimate (Sweep+SMT+VWAP+H1+FVG)"

    if not sig:
        return None

    # Calculate Entry, SL, and Dual-Exit
    sl_buf = max(0.20 * atr, 0.25)
    scalp_rr = 1.8

    # Dynamic Runner Target (Expands to 4.5R when ATR is elevated)
    runner_rr = 4.5 if atr >= 2.5 else 3.5

    if sig == "BUY":
        sl = round(cur['low'] - sl_buf, 2)
        entry = round(cur['low'] + (retest_depth * cur['lower_wick']), 2)
        risk = entry - sl
        if risk <= 0:
            return None
        tp_scalp = round(entry + (risk * scalp_rr), 2)
        macro_target = cur['opposite_high_40']
        tp_runner = round(max(macro_target, entry + (risk * runner_rr)), 2)
    else:
        sl = round(cur['high'] + sl_buf, 2)
        entry = round(cur['high'] - (retest_depth * cur['upper_wick']), 2)
        risk = sl - entry
        if risk <= 0:
            return None
        tp_scalp = round(entry - (risk * scalp_rr), 2)
        macro_target = cur['opposite_low_40']
        tp_runner = round(min(macro_target, entry - (risk * runner_rr)), 2)

    return {
        "time": cur['time'],
        "time_str": str(cur['time_dt']),
        "signal": sig,
        "mode": mode,
        "reason": reason,
        "entry": entry,
        "sl": sl,
        "risk": risk,
        "tp_scalp": tp_scalp,
        "tp_runner": tp_runner,
        "vol_ratio": cur['vol_ratio'],
        "wick_pct": cur['lower_wick_pct'] if sig == "BUY" else cur['upper_wick_pct'],
        "be_ratio": 0.40
    }
