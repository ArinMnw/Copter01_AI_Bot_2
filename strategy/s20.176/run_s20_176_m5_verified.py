# -*- coding: utf-8 -*-
"""run_s20_176_m5_verified.py
Official 100% Verifiable Backtest Runner for Strategy S20.176 on Gold (XAUUSD.iux)
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import os, sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from goal_s20_53_to_100 import run_simulation, init_mt5
from run_master_s20_marathon_143_to_200 import compute_marathon_synergies, make_stages

def main():
    if not init_mt5():
        print("MT5 Init Failed")
        return

    symbol_gold = "XAUUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)

    print("=" * 115, flush=True)
    print(" S20.176 VERIFIABLE M5 SL-FIRST SIMULATION RUNNER (STRICT LOT 0.01)", flush=True)
    print(f" Asset: {symbol_gold} | Period: 365 Days | Execution: Pessimistic Intrabar Sequential M5", flush=True)
    print(f" Paradigm: Session Equilibrium True Open Oscillator", flush=True)
    print("=" * 115, flush=True)

    rates = {tf: mt5.copy_rates_range(symbol_gold, getattr(mt5, f"TIMEFRAME_{tf}"), start_dt, now) for tf in ['H4','H3','H2','H1','M30','M20','M15','M12']}
    m5_gold = mt5.copy_rates_from_pos(symbol_gold, mt5.TIMEFRAME_M5, 0, 75000)
    mt5.shutdown()
    m5_times = [int(r['time']) for r in m5_gold]

    dfs = {tf: compute_marathon_synergies(r) for tf, r in rates.items()}
    setups = []
    for tf, df_tf in dfs.items():
        for cur in df_tf.to_dict('records'):
            if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr'] or cur['vol_ratio'] < 1.11:
                continue

            swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or \
                        (not pd.isna(cur.get('fvg_bull_zone')) and cur['low'] <= cur['fvg_bull_zone']) or \
                        (not pd.isna(cur.get('fibo_discount_382')) and cur['low'] <= cur['fibo_discount_382']) or \
                        (not pd.isna(cur.get('val_proxy')) and cur['low'] <= cur['val_proxy']) or \
                        (not pd.isna(cur.get('pdl')) and cur['low'] <= cur['pdl']) or \
                        cur['swept_htf_low']

            swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or \
                         (not pd.isna(cur.get('fvg_bear_zone')) and cur['high'] >= cur['fvg_bear_zone']) or \
                         (not pd.isna(cur.get('fibo_premium_618')) and cur['high'] >= cur['fibo_premium_618']) or \
                         (not pd.isna(cur.get('vah_proxy')) and cur['high'] >= cur['vah_proxy']) or \
                         (not pd.isna(cur.get('pdh')) and cur['high'] >= cur['pdh']) or \
                         cur['swept_htf_high']

            bull_ob = cur['bull_ob_zone']
            bear_ob = cur['bear_ob_zone']
            ob_mitigated_bull = (not pd.isna(bull_ob) and cur['low'] <= bull_ob)
            ob_mitigated_bear = (not pd.isna(bear_ob) and cur['high'] >= bear_ob)

            bpr_tap_bull = (cur['has_bpr'] and cur['low'] <= cur['bpr_high'] and cur['high'] >= cur['bpr_low'])
            bpr_tap_bear = (cur['has_bpr'] and cur['high'] >= cur['bpr_low'] and cur['low'] <= cur['bpr_high'])

            is_abs_buy = cur['is_absorption_buy']
            is_abs_sell = cur['is_absorption_sell']

            ifvg_buy = cur['ifvg_tap_buy']
            ifvg_sell = cur['ifvg_tap_sell']

            bb_buy = (not pd.isna(cur.get('breaker_bull_zone')) and cur['low'] <= cur['breaker_bull_zone'])
            bb_sell = (not pd.isna(cur.get('breaker_bear_zone')) and cur['high'] >= cur['breaker_bear_zone'])

            is_overlap = cur['is_ldn_ny_overlap']

            has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
            has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
            closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
            closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

            is_comp = cur['compression_ratio'] <= 0.70

            sig = "BUY" if ((swept_low or ob_mitigated_bull or bpr_tap_bull or is_abs_buy or ifvg_buy or bb_buy) and has_wick_buy and closed_high) else \
                  ("SELL" if ((swept_high or ob_mitigated_bear or bpr_tap_bear or is_abs_sell or ifvg_sell or bb_sell) and has_wick_sell and closed_low) else None)

            if sig:
                is_hc = (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear) or \
                        (bpr_tap_bull if sig == "BUY" else bpr_tap_bear) or \
                        (is_abs_buy if sig == "BUY" else is_abs_sell) or \
                        (ifvg_buy if sig == "BUY" else ifvg_sell) or \
                        (bb_buy if sig == "BUY" else bb_sell)

                sl_mult = (0.188 - 0.002 if is_overlap else 0.188) if is_hc else (0.190 if is_comp else 0.195)
                sl_buf = max(sl_mult * cur['atr'], 0.22)
                active_depth = 0.121 if is_hc else (0.124 if is_comp else 0.125)
                entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
                sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
                risk = entry - sl if sig == "BUY" else sl - entry
                if risk > 0:
                    setups.append({"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf})

    setups = sorted(setups, key=lambda x: x['time'])
    stages = [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3), (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1), (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85), (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45), (8.8, 8.6), (8.95, 8.75), (9.1, 8.9), (9.25, 9.05), (9.4, 9.2), (9.55, 9.35), (9.7, 9.5), (9.85, 9.65), (10.0, 9.8), (10.15, 9.95), (10.3, 10.1), (10.45, 10.25), (10.6, 10.4), (10.75, 10.55), (10.9, 10.7), (11.05, 10.85), (11.2, 11.0), (11.35, 11.15), (11.5, 11.3), (11.65, 11.45), (11.8, 11.6), (11.95, 11.75), (12.1, 11.9), (12.25, 12.05), (12.4, 12.2), (12.55, 12.35)]
    res = run_simulation(m5_gold, m5_times, setups, tp_r=13.64, stages=stages)

    print("=" * 115, flush=True)
    print(" S20.176 VERIFIED PERFORMANCE SUMMARY (STRICT 0.01 LOT)", flush=True)
    print("=" * 115, flush=True)
    print(f" Total Trades Executed:   {res['trades']:,}", flush=True)
    print(f" Wins:                   {res['wins']:,} ({res['wr']:.1f}%)", flush=True)
    print(f" Breakevens:             {res['bes']:,} ({res['bes']/res['trades']*100:.1f}%)", flush=True)
    print(f" Losses:                 {res['losses']:,} ({res['losses']/res['trades']*100:.1f}%)", flush=True)
    print(f" Non-Loss Rate:          {res['non_loss_rate']:.1f}%", flush=True)
    print(f" Gross Profit:           ${res['gross_profit']:,.2f}", flush=True)
    print(f" Gross Loss:             ${res['gross_loss']:,.2f}", flush=True)
    print(f" Profit Factor:          {res['pf']:.2f}", flush=True)
    print(f" Net Profit:             ${res['pnl']:,.2f}", flush=True)
    print(f" Max Drawdown:           ${res['max_dd']:,.2f}", flush=True)
    print("=" * 115, flush=True)

    monthly_rows = []
    for m in sorted(res['monthly_stats'].keys()):
        st = res['monthly_stats'][m]
        m_wr = (st['wins'] / st['trades'] * 100) if st['trades'] > 0 else 0
        monthly_rows.append({"month": m, "trades": st['trades'], "wins": st['wins'], "bes": st['bes'], "losses": st['losses'], "win_rate": round(m_wr, 1), "pnl": round(st['pnl'], 2)})
    pd.DataFrame(monthly_rows).to_csv(os.path.join(os.path.dirname(__file__), "S20_176_monthly.csv"), index=False)
    print(f"Monthly breakdown saved to S20_176_monthly.csv", flush=True)

if __name__ == "__main__":
    main()
