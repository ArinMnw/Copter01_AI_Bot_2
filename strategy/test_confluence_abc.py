# -*- coding: utf-8 -*-
"""test_confluence_abc.py
Experimenting genuine new multi-strategy cross-breed paradigms:
- Strategy S20.101 (Concept A: Order Flow CVD / Volume Delta Exhaustion + Sweep Confluence)
- Strategy S20.102 (Concept B: London/NY Opening Judas Swing + Volume Climax Absorption)
- Strategy S20.103 (Concept C: Volatility Regime Filter - Adaptive Expansion/Compression)

Strict Mandates:
- Strict 0.01 lot single position ($1.00/pt) throughout 365 days
- Zero look-ahead bias, causal shift(1)
- Pessimistic SL-First sequential execution on 75,000+ M5 bars
- Realistic 2-hour limit retest timeout
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import bisect
from datetime import datetime, timedelta, timezone
import os, sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

from goal_s20_53_to_100 import compute_indicators, run_simulation, init_mt5

def compute_advanced_features(rates, fvg_depth=5):
    # Get base indicators
    df = compute_indicators(rates, use_london=True, use_ny=True, use_ny_pm=True, fvg_depth=fvg_depth)
    
    # 1. Concept A: Cumulative Volume Delta (CVD Proxy via Tick Volume & Bar Price Action)
    # Delta approximation: Volume * ((Close - Open) / (High - Low + 1e-5))
    bar_direction = (df['close'] - df['open']) / (df['range'] + 1e-5)
    df['bar_delta'] = df['tick_volume'] * bar_direction
    df['cvd_20'] = df['bar_delta'].rolling(20).sum()
    df['cvd_ma20'] = df['cvd_20'].rolling(20).mean()
    # Delta exhaustion: Price makes higher high than previous 12 bars, but CVD fails to make higher high (Bearish CVD Div)
    # Price makes lower low than previous 12 bars, but CVD fails to make lower low (Bullish CVD Div)
    df['cvd_min_12'] = df['cvd_20'].rolling(12).min().shift(1)
    df['cvd_max_12'] = df['cvd_20'].rolling(12).max().shift(1)
    
    # 2. Concept B: Session Judas Swing Timing
    # Judas Swing happens specifically at Session Openings:
    # London Open Killzone: 07:00 - 10:00 UTC
    # NY Open Killzone: 12:00 - 15:00 UTC
    df['is_london_judas'] = (df['hour'] >= 7) & (df['hour'] <= 10)
    df['is_ny_judas'] = (df['hour'] >= 12) & (df['hour'] <= 15)
    df['is_judas_window'] = df['is_london_judas'] | df['is_ny_judas']

    # 3. Concept C: Volatility Regime (Parkinson / ATR Ratio)
    # High-vol expansion regime vs Low-vol compression regime
    df['atr_ma50'] = df['atr'].rolling(50).mean()
    df['vol_regime_ratio'] = df['atr'] / (df['atr_ma50'] + 1e-5)
    # Bollinger Band Width
    rolling_mean = df['close'].rolling(20).mean()
    rolling_std = df['close'].rolling(20).std()
    df['bb_width'] = (2.0 * rolling_std) / (rolling_mean + 1e-5)
    df['bb_width_ma50'] = df['bb_width'].rolling(50).mean()
    df['is_vol_expansion'] = df['bb_width'] > df['bb_width_ma50']

    return df

def test_paradigms():
    if not init_mt5():
        print("MT5 Init Failed")
        return

    symbol_gold = "XAUUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)
    timeframes = ['H4','H3','H2','H1','M30','M20','M15','M12']
    rates = {tf: mt5.copy_rates_range(symbol_gold, getattr(mt5, f"TIMEFRAME_{tf}"), start_dt, now) for tf in timeframes}
    m5_gold = mt5.copy_rates_from_pos(symbol_gold, mt5.TIMEFRAME_M5, 0, 75000)
    mt5.shutdown()
    m5_times = [int(r['time']) for r in m5_gold]

    print("Computing advanced multi-paradigm features...", flush=True)
    dfs = {tf: compute_advanced_features(r) for tf, r in rates.items()}

    # Base S20.100 stages (29 stages, TP 8.75R)
    base_stages = [
        (1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5),
        (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4),
        (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3),
        (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1),
        (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85),
        (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45)
    ]

    print("\n" + "="*80)
    print("TESTING PARADIGMS WITH FULL M5 PESSIMISTIC SL-FIRST ENGINE")
    print("="*80)

    # 1. Test Concept A (Order Flow CVD Divergence Confluence)
    for cvd_weight in [True, False]:
        for min_v in [1.12, 1.15]:
            setups_a = []
            for tf, df_tf in dfs.items():
                recs = df_tf.to_dict('records')
                for idx in range(45, len(recs)):
                    cur = recs[idx]
                    if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr']:
                        continue
                    if cur['vol_ratio'] < min_v:
                        continue
                    # CVD Confluence:
                    # For BUY: Swept low + Bullish CVD divergence (CVD did not make a new low)
                    # For SELL: Swept high + Bearish CVD divergence (CVD did not make a new high)
                    bull_cvd_div = cur['cvd_20'] > cur['cvd_min_12']
                    bear_cvd_div = cur['cvd_20'] < cur['cvd_max_12']
                    
                    # Core SMC / FVG / Fibo / VP sweeps
                    swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or (not pd.isna(cur['fvg_bull_zone']) and cur['low'] <= cur['fvg_bull_zone']) or (not pd.isna(cur['fibo_discount_382']) and cur['low'] <= cur['fibo_discount_382'])
                    swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or (not pd.isna(cur['fvg_bear_zone']) and cur['high'] >= cur['fvg_bear_zone']) or (not pd.isna(cur['fibo_premium_618']) and cur['high'] >= cur['fibo_premium_618'])
                    
                    has_wick_buy = (cur['lower_wick_pct'] >= 0.12) or (cur['lower_wick'] >= 1.1 * cur['body'])
                    has_wick_sell = (cur['upper_wick_pct'] >= 0.12) or (cur['upper_wick'] >= 1.1 * cur['body'])
                    
                    sig = None
                    if swept_low and has_wick_buy and (not cvd_weight or bull_cvd_div):
                        sig = "BUY"
                    elif swept_high and has_wick_sell and (not cvd_weight or bear_cvd_div):
                        sig = "SELL"
                        
                    if sig:
                        sl_buf = max(0.20 * cur['atr'], 0.22)
                        if sig == "BUY":
                            sl = round(cur['low'] - sl_buf, 2)
                            entry = round(cur['low'] + (0.125 * cur['lower_wick']), 2)
                            risk = entry - sl
                        else:
                            sl = round(cur['high'] + sl_buf, 2)
                            entry = round(cur['high'] - (0.125 * cur['upper_wick']), 2)
                            risk = sl - entry
                        if risk > 0:
                            setups_a.append({
                                "time": int(cur['time']),
                                "signal": sig,
                                "entry": entry,
                                "sl": sl,
                                "risk": risk,
                                "atr": cur['atr'],
                                "tf": tf
                            })
            setups_a = sorted(setups_a, key=lambda x: x['time'])
            res_a = run_simulation(m5_gold, m5_times, setups_a, tp_r=8.75, stages=base_stages)
            print(f"[Concept A: CVD={cvd_weight} v={min_v}] PnL: ${res_a['pnl']:,.2f} | Trades: {res_a['trades']} | WR: {res_a['wr']:.1f}% | DD: ${res_a['max_dd']:.2f}")

    # 2. Test Concept B (Session Judas Swing Timing)
    for judas_only in [True, False]:
        setups_b = []
        for tf, df_tf in dfs.items():
            recs = df_tf.to_dict('records')
            for idx in range(45, len(recs)):
                cur = recs[idx]
                if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr']:
                    continue
                if judas_only and not cur['is_judas_window']:
                    continue
                if cur['vol_ratio'] < 1.15:
                    continue
                swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or (not pd.isna(cur['fvg_bull_zone']) and cur['low'] <= cur['fvg_bull_zone'])
                swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or (not pd.isna(cur['fvg_bear_zone']) and cur['high'] >= cur['fvg_bear_zone'])
                has_wick_buy = (cur['lower_wick_pct'] >= 0.12)
                has_wick_sell = (cur['upper_wick_pct'] >= 0.12)
                sig = "BUY" if (swept_low and has_wick_buy) else ("SELL" if (swept_high and has_wick_sell) else None)
                if sig:
                    sl_buf = max(0.20 * cur['atr'], 0.22)
                    entry = round(cur['low'] + (0.125 * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (0.125 * cur['upper_wick']), 2)
                    sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
                    risk = entry - sl if sig == "BUY" else sl - entry
                    if risk > 0:
                        setups_b.append({"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf})
        setups_b = sorted(setups_b, key=lambda x: x['time'])
        res_b = run_simulation(m5_gold, m5_times, setups_b, tp_r=8.75, stages=base_stages)
        print(f"[Concept B: JudasOnly={judas_only}] PnL: ${res_b['pnl']:,.2f} | Trades: {res_b['trades']} | WR: {res_b['wr']:.1f}% | DD: ${res_b['max_dd']:.2f}")

    # 3. Test Concept C (Volatility Regime Gate)
    for regime_filter in [True, False]:
        setups_c = []
        for tf, df_tf in dfs.items():
            recs = df_tf.to_dict('records')
            for idx in range(45, len(recs)):
                cur = recs[idx]
                if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr']:
                    continue
                if regime_filter and not cur['is_vol_expansion']:
                    continue
                if cur['vol_ratio'] < 1.15:
                    continue
                swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or (not pd.isna(cur['fvg_bull_zone']) and cur['low'] <= cur['fvg_bull_zone'])
                swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or (not pd.isna(cur['fvg_bear_zone']) and cur['high'] >= cur['fvg_bear_zone'])
                has_wick_buy = (cur['lower_wick_pct'] >= 0.12)
                has_wick_sell = (cur['upper_wick_pct'] >= 0.12)
                sig = "BUY" if (swept_low and has_wick_buy) else ("SELL" if (swept_high and has_wick_sell) else None)
                if sig:
                    sl_buf = max(0.20 * cur['atr'], 0.22)
                    entry = round(cur['low'] + (0.125 * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (0.125 * cur['upper_wick']), 2)
                    sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
                    risk = entry - sl if sig == "BUY" else sl - entry
                    if risk > 0:
                        setups_c.append({"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf})
        setups_c = sorted(setups_c, key=lambda x: x['time'])
        res_c = run_simulation(m5_gold, m5_times, setups_c, tp_r=8.75, stages=base_stages)
        print(f"[Concept C: VolExpansionOnly={regime_filter}] PnL: ${res_c['pnl']:,.2f} | Trades: {res_c['trades']} | WR: {res_c['wr']:.1f}% | DD: ${res_c['max_dd']:.2f}")

if __name__ == "__main__":
    test_paradigms()
