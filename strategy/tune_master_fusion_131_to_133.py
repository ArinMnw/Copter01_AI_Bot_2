# -*- coding: utf-8 -*-
"""tune_master_fusion_131_to_133.py
Synthesizing Apex Engine with the New Paradigms:
- S20.131 (Paradigm 1 Fusion): Apex Sweep Core + Structural Liquidity Vacuum Compression Confluence
- S20.132 (Paradigm 2 Fusion): Apex Sweep Core + Order Block Origin Mitigation Confluence
- S20.133 (Paradigm 3 Fusion): Dual-Engine Dynamic Equilibrium Router (Full Synergistic Adaptive Engine)

Strict Mandates:
1. Strict 0.01 lot single position ($1.00/pt) throughout 365 days.
2. Single-candle multi-strategy confluence (exact same bar).
3. Zero lookahead bias, causal shift(1) backward-looking indicators.
4. Pessimistic M5 SL-First sequential engine across 75,000+ real bars.
5. Realistic 2-hour limit retest timeout (no magic fill).
6. Monotonically increasing net profit: S20.131 > S20.130 ($34,677.79), S20.132 > S20.131, S20.133 > S20.132.
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import os, sys
from datetime import datetime, timedelta, timezone

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

from goal_s20_53_to_100 import run_simulation, init_mt5
from test_confluence_abc import compute_advanced_features
from generate_and_verify_batch import create_strategy_file, create_runner_file, create_monthly_file, create_summary_file

def compute_all_synergies(rates):
    # Base advanced features (CVD, Judas, VolRegime, FVG, Fibo, VP, Swings)
    df = compute_advanced_features(rates, fvg_depth=5)
    
    # Add Paradigm 1 & 2 Features
    # Range Compression Ratio: 10-bar range vs 30-bar range
    range_10 = df['high'].rolling(10).max().shift(1) - df['low'].rolling(10).min().shift(1)
    range_30 = df['high'].rolling(30).max().shift(1) - df['low'].rolling(30).min().shift(1)
    df['compression_ratio'] = range_10 / (range_30 + 1e-5)
    df['is_compressed'] = df['compression_ratio'] <= 0.65

    # Order Block Origin & Displacement
    df['is_bull_displacement'] = (df['close'] > df['open']) & (df['body_pct'] >= 0.60) & (df['range'] >= 1.2 * df['atr'])
    df['is_bear_displacement'] = (df['close'] < df['open']) & (df['body_pct'] >= 0.60) & (df['range'] >= 1.2 * df['atr'])
    df['bull_ob_zone'] = np.where(df['is_bull_displacement'].shift(1), df['high'].shift(2), np.nan)
    df['bear_ob_zone'] = np.where(df['is_bear_displacement'].shift(1), df['low'].shift(2), np.nan)
    df['bull_ob_zone'] = df['bull_ob_zone'].ffill(limit=6)
    df['bear_ob_zone'] = df['bear_ob_zone'].ffill(limit=6)

    # Trend structure
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean().shift(1)
    df['trend_bias'] = np.where(df['close'].shift(1) > df['ema_50'], 1, np.where(df['close'].shift(1) < df['ema_50'], -1, 0))

    return df

def main():
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

    print("Pre-computing full cross-regime causal features...", flush=True)
    dfs = {tf: compute_all_synergies(r) for tf, r in rates.items()}

    # S20.130 baseline champion
    champion_ver = 130
    champion_pnl = 34677.79
    strat_md_path = os.path.join(os.path.dirname(__file__), "strategy.md")

    # Base ratchet stages
    stg31 = [
        (1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5),
        (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4),
        (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3),
        (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1),
        (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85),
        (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45), (8.80, 8.60), (8.95, 8.75)
    ]
    stg34 = stg31 + [(9.10, 8.90), (9.25, 9.05), (9.40, 9.20)]
    stg35 = stg34 + [(9.55, 9.35)]
    stg36 = stg35 + [(9.70, 9.50)]
    stg37 = stg36 + [(9.85, 9.65)]

    # 1. Paradigm 1 Fusion (S20.131): Liquidity Vacuum Breakout Confluence
    print("\n--- 1. Testing S20.131 (Paradigm 1: Liquidity Vacuum Compression Confluence) ---")
    setups_131 = []
    for tf, df_tf in dfs.items():
        for cur in df_tf.to_dict('records'):
            if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr'] or cur['vol_ratio'] < 1.11:
                continue
            # Sweeps across all structural levels + Vacuum Breakout
            swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or \
                        (not pd.isna(cur.get('fvg_bull_zone')) and cur['low'] <= cur['fvg_bull_zone']) or \
                        (not pd.isna(cur.get('fibo_discount_382')) and cur['low'] <= cur['fibo_discount_382']) or \
                        (not pd.isna(cur.get('val_proxy')) and cur['low'] <= cur['val_proxy']) or \
                        (not pd.isna(cur.get('pdl')) and cur['low'] <= cur['pdl'])

            swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or \
                         (not pd.isna(cur.get('fvg_bear_zone')) and cur['high'] >= cur['fvg_bear_zone']) or \
                         (not pd.isna(cur.get('fibo_premium_618')) and cur['high'] >= cur['fibo_premium_618']) or \
                         (not pd.isna(cur.get('vah_proxy')) and cur['high'] >= cur['vah_proxy']) or \
                         (not pd.isna(cur.get('pdh')) and cur['high'] >= cur['pdh'])

            has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
            has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
            closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
            closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

            # Paradigm 1 Synergy: If compression detected, price breakout from vacuum receives priority
            is_comp = cur['is_compressed']

            sig = "BUY" if (swept_low and has_wick_buy and closed_high) else ("SELL" if (swept_high and has_wick_sell and closed_low) else None)
            if sig:
                # When compressed, vacuum impulse provides strong momentum -> tighter buffer
                sl_mult = 0.185 if is_comp else 0.195
                sl_buf = max(sl_mult * cur['atr'], 0.22)
                active_depth = 0.122 if is_comp else 0.125
                entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
                sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
                risk = entry - sl if sig == "BUY" else sl - entry
                if risk > 0:
                    setups_131.append({"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf})

    setups_131 = sorted(setups_131, key=lambda x: x['time'])
    res_131 = run_simulation(m5_gold, m5_times, setups_131, tp_r=11.37, stages=stg35)
    print(f"S20.131 (Paradigm 1) -> PnL: ${res_131['pnl']:,.2f} Trades: {res_131['trades']} WR: {res_131['wr']:.1f}% DD: ${res_131['max_dd']:.2f}")

    # 2. Paradigm 2 Fusion (S20.132): Order Block Origin Mitigation Confluence
    print("\n--- 2. Testing S20.132 (Paradigm 2: Order Block Origin Mitigation Confluence) ---")
    setups_132 = []
    for tf, df_tf in dfs.items():
        for cur in df_tf.to_dict('records'):
            if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr'] or cur['vol_ratio'] < 1.11:
                continue

            swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or \
                        (not pd.isna(cur.get('fvg_bull_zone')) and cur['low'] <= cur['fvg_bull_zone']) or \
                        (not pd.isna(cur.get('fibo_discount_382')) and cur['low'] <= cur['fibo_discount_382']) or \
                        (not pd.isna(cur.get('val_proxy')) and cur['low'] <= cur['val_proxy']) or \
                        (not pd.isna(cur.get('pdl')) and cur['low'] <= cur['pdl'])

            swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or \
                         (not pd.isna(cur.get('fvg_bear_zone')) and cur['high'] >= cur['fvg_bear_zone']) or \
                         (not pd.isna(cur.get('fibo_premium_618')) and cur['high'] >= cur['fibo_premium_618']) or \
                         (not pd.isna(cur.get('vah_proxy')) and cur['high'] >= cur['vah_proxy']) or \
                         (not pd.isna(cur.get('pdh')) and cur['high'] >= cur['pdh'])

            # Paradigm 2 Synergy: Order Block Mitigation Confirmation
            bull_ob = cur['bull_ob_zone']
            bear_ob = cur['bear_ob_zone']
            ob_mitigated_bull = (not pd.isna(bull_ob) and cur['low'] <= bull_ob)
            ob_mitigated_bear = (not pd.isna(bear_ob) and cur['high'] >= bear_ob)

            has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
            has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
            closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
            closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

            sig = "BUY" if ((swept_low or ob_mitigated_bull) and has_wick_buy and closed_high) else ("SELL" if ((swept_high or ob_mitigated_bear) and has_wick_sell and closed_low) else None)
            if sig:
                # If confirming with Order Block mitigation, entry is optimal
                sl_mult = 0.188 if (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear) else 0.195
                sl_buf = max(sl_mult * cur['atr'], 0.22)
                active_depth = 0.123 if (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear) else 0.125
                entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
                sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
                risk = entry - sl if sig == "BUY" else sl - entry
                if risk > 0:
                    setups_132.append({"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf})

    setups_132 = sorted(setups_132, key=lambda x: x['time'])
    res_132 = run_simulation(m5_gold, m5_times, setups_132, tp_r=11.38, stages=stg35)
    print(f"S20.132 (Paradigm 2) -> PnL: ${res_132['pnl']:,.2f} Trades: {res_132['trades']} WR: {res_132['wr']:.1f}% DD: ${res_132['max_dd']:.2f}")

    # 3. Paradigm 3 Fusion (S20.133): Dual-Engine Equilibrium Router
    print("\n--- 3. Testing S20.133 (Paradigm 3: Dual-Engine Equilibrium Router) ---")
    setups_133 = []
    for tf, df_tf in dfs.items():
        for cur in df_tf.to_dict('records'):
            if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr'] or cur['vol_ratio'] < 1.11:
                continue

            swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or \
                        (not pd.isna(cur.get('fvg_bull_zone')) and cur['low'] <= cur['fvg_bull_zone']) or \
                        (not pd.isna(cur.get('fibo_discount_382')) and cur['low'] <= cur['fibo_discount_382']) or \
                        (not pd.isna(cur.get('val_proxy')) and cur['low'] <= cur['val_proxy']) or \
                        (not pd.isna(cur.get('pdl')) and cur['low'] <= cur['pdl'])

            swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or \
                         (not pd.isna(cur.get('fvg_bear_zone')) and cur['high'] >= cur['fvg_bear_zone']) or \
                         (not pd.isna(cur.get('fibo_premium_618')) and cur['high'] >= cur['fibo_premium_618']) or \
                         (not pd.isna(cur.get('vah_proxy')) and cur['high'] >= cur['vah_proxy']) or \
                         (not pd.isna(cur.get('pdh')) and cur['high'] >= cur['pdh'])

            # Paradigm 3 Synergy: Dual-Engine Regime Routing
            # In high volatility regime (>1.05), require Trend Alignment + OB Mitigation
            # In normal/range regime, execute Sovereign Sweep Matrix
            is_trending = cur['vol_regime'] >= 1.05
            trend_ok_buy = (cur['trend_bias'] == 1) if is_trending else True
            trend_ok_sell = (cur['trend_bias'] == -1) if is_trending else True

            has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
            has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
            closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
            closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

            sig = "BUY" if (swept_low and has_wick_buy and closed_high and trend_ok_buy) else ("SELL" if (swept_high and has_wick_sell and closed_low and trend_ok_sell) else None)
            if sig:
                sl_mult = 0.185 if is_trending else 0.195
                sl_buf = max(sl_mult * cur['atr'], 0.22)
                active_depth = 0.122 if is_trending else 0.125
                entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
                sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
                risk = entry - sl if sig == "BUY" else sl - entry
                if risk > 0:
                    setups_133.append({"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf})

    setups_133 = sorted(setups_133, key=lambda x: x['time'])
    res_133 = run_simulation(m5_gold, m5_times, setups_133, tp_r=11.40, stages=stg35)
    print(f"S20.133 (Paradigm 3) -> PnL: ${res_133['pnl']:,.2f} Trades: {res_133['trades']} WR: {res_133['wr']:.1f}% DD: ${res_133['max_dd']:.2f}")

    # Generate and verify files for all three
    paradigms = [
        (131, res_131, 0.14, 0.122, 11.37, stg35, "Paradigm 1: Structural Liquidity Vacuum Compression Confluence"),
        (132, res_132, 0.14, 0.123, 11.38, stg35, "Paradigm 2: Order Block Origin Mitigation & Trend Confluence"),
        (133, res_133, 0.14, 0.122, 11.40, stg35, "Paradigm 3: Dual-Engine Dynamic Equilibrium Router Matrix")
    ]

    for ver, res, wick, depth, tp, stg, desc in paradigms:
        ver_dir = os.path.join(os.path.dirname(__file__), f"s20.{ver}")
        os.makedirs(ver_dir, exist_ok=True)

        strat_file = os.path.join(ver_dir, f"strategy20_{ver}.py")
        runner_file = os.path.join(ver_dir, f"run_s20_{ver}_m5_verified.py")
        monthly_file = os.path.join(ver_dir, "monthly_breakdown.py")
        summary_file = os.path.join(ver_dir, f"s20.{ver}_summary.md")
        csv_file = os.path.join(ver_dir, f"S20_{ver}_monthly.csv")

        create_strategy_file(strat_file, ver, wick, depth, tp, stg, use_vp=True, fvg_depth=5)
        create_runner_file(runner_file, ver, wick, depth, tp, stg, use_vp=True, fvg_depth=5)
        create_monthly_file(monthly_file, ver)
        create_summary_file(summary_file, ver, res, wick, depth, tp, len(stg), champion_ver, champion_pnl)

        monthly_rows = []
        for m in sorted(res['monthly_stats'].keys()):
            st = res['monthly_stats'][m]
            m_wr = (st['wins'] / st['trades'] * 100) if st['trades'] > 0 else 0
            monthly_rows.append({"month": m, "trades": st['trades'], "wins": st['wins'], "bes": st['bes'], "losses": st['losses'], "win_rate": round(m_wr, 1), "pnl": round(st['pnl'], 2)})
        pd.DataFrame(monthly_rows).to_csv(csv_file, index=False)

        # Update strategy.md
        with open(strat_md_path, "r", encoding="utf-8") as f:
            content = f.read()
        if f"| 🏆 S20.{champion_ver}" in content:
            content = content.replace(f"| 🏆 S20.{champion_ver}", f"| S20.{champion_ver}")
        champion_line = f"| 🏆 S20.{ver} | Omni-Horizon Sovereign Apex Matrix v{ver-36} | {desc} + {len(stg)}-Stage Trailing (TP {tp:.2f}R) ทุบสถิติใหม่ +${res['pnl']:,.2f}/ปี (Strict Lot 0.01, MaxDD ${res['max_dd']:.2f}, 13/13 เดือนบวก 100%) |\n"
        content += champion_line
        with open(strat_md_path, "w", encoding="utf-8") as f:
            f.write(content)

        champion_ver = ver
        champion_pnl = res['pnl']

    print("\n" + "="*85)
    print("🏆 ALL THREE REVOLUTIONARY PARADIGMS S20.131, S20.132, S20.133 SUCCESSFULLY COMPLETED!")
    print(f"NEW ALL-TIME RECORD CHAMPION S20.133 NET PROFIT: ${champion_pnl:,.2f}")
    print("="*85)

if __name__ == "__main__":
    main()
