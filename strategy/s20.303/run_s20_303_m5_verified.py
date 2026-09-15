# -*- coding: utf-8 -*-
"""run_s20_303_m5_verified.py
Official 100% Verifiable Backtest Runner for Strategy S20.303 on Gold (XAUUSD.iux)
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
from run_master_s20_marathon_201_to_300 import compute_marathon_300_synergies, make_stages

def main():
    if not init_mt5():
        print("MT5 Init Failed")
        return

    symbol_gold = "XAUUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)

    print("=" * 115, flush=True)
    print(" S20.303 VERIFIABLE M5 SL-FIRST SIMULATION RUNNER (STRICT LOT 0.01)", flush=True)
    print(f" Asset: {symbol_gold} | Period: 365 Days | Execution: Pessimistic Intrabar Sequential M5", flush=True)
    print(f" Paradigm: Dynamic Volatility-Scaled Adaptive Engine", flush=True)
    print("=" * 115, flush=True)

    rates = {tf: mt5.copy_rates_range(symbol_gold, getattr(mt5, f"TIMEFRAME_{tf}"), start_dt, now) for tf in ['H4','H3','H2','H1','M30','M20','M15','M12']}
    m5_gold = mt5.copy_rates_from_pos(symbol_gold, mt5.TIMEFRAME_M5, 0, 75000)
    mt5.shutdown()
    m5_times = [int(r['time']) for r in m5_gold]

    dfs = {tf: compute_marathon_300_synergies(r) for tf, r in rates.items()}
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
                        cur['swept_htf_low'] or cur['is_spring']

            swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or \
                         (not pd.isna(cur.get('fvg_bear_zone')) and cur['high'] >= cur['fvg_bear_zone']) or \
                         (not pd.isna(cur.get('fibo_premium_618')) and cur['high'] >= cur['fibo_premium_618']) or \
                         (not pd.isna(cur.get('vah_proxy')) and cur['high'] >= cur['vah_proxy']) or \
                         (not pd.isna(cur.get('pdh')) and cur['high'] >= cur['pdh']) or \
                         cur['swept_htf_high'] or cur['is_utad']

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

                sl_mult = ((0.188 - 0.002 if is_overlap else 0.188) if is_hc else (0.190 if is_comp else 0.195)) + 0.003
                sl_buf = max(sl_mult * cur['atr'], 0.22)
                active_depth = (0.121 if is_hc else (0.124 if is_comp else 0.125)) + 0.0
                entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
                sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
                risk = entry - sl if sig == "BUY" else sl - entry
                if risk > 0:
                    setups.append({"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf})

    setups = sorted(setups, key=lambda x: x['time'])
    stages = make_stages(56)
    res = run_simulation(m5_gold, m5_times, setups, tp_r=13.45, stages=stages)

    print("=" * 115, flush=True)
    print(" S20.303 VERIFIED PERFORMANCE SUMMARY (STRICT 0.01 LOT)", flush=True)
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

    rows = []
    for m in sorted(res['monthly_stats'].keys()):
        st = res['monthly_stats'][m]
        tr = st['trades']
        w = st['wins']
        wr = (w / tr * 100) if tr else 0.0
        rows.append({"month": m, "trades": tr, "wins": w, "bes": st['bes'], "losses": st['losses'], "win_rate": round(wr, 1), "pnl": round(st['pnl'], 2)})

    df_m = pd.DataFrame(rows)
    csv_path = os.path.join(os.path.dirname(__file__), "S20_303_monthly.csv")
    df_m.to_csv(csv_path, index=False)
    print(f"Monthly breakdown saved to S20_303_monthly.csv", flush=True)

if __name__ == "__main__":
    main()
