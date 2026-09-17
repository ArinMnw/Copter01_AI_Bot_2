# -*- coding: utf-8 -*-
"""test_rebuild_s20_304.py
Testing Rebuilt S20.304 with Quant Verification Checklist Rules:
- Rule #6: Minimum Viable SL Buffer (>= 1.5 USD on Gold, >= 0.10 on Silver) to keep Spread/SL < 10%
- Rule #7: Limit Penetration (Touch is not a fill)
- Rule #8: Real Bid/Ask Spread
- Rule #9: Negative Slippage on SL
- Rule #10: Timeframe-proportional expiration
"""
import sys, os, bisect
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5

root_dir = r"d:\Project\Copter01_AI_Bot_2"
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, "strategy"))
sys.path.append(os.path.join(root_dir, "strategy", "s20.304"))

from run_master_s20_marathon_201_to_300 import compute_marathon_300_synergies
from audit_s20_304_quant import run_quant_simulation, summarize

def extract_rebuilt_setups(symbol, dfs, digits, point, min_sl_usd=1.50):
    setups = []
    sym_upper = symbol.upper()
    is_gold = "XAU" in sym_upper
    
    # Quantitative parameters matching Checklist
    min_sl = min_sl_usd if is_gold else (min_sl_usd * 0.08) # Silver ~0.12 USD
    
    for tf, df_tf in dfs.items():
        if df_tf is None or len(df_tf) == 0:
            continue
        for cur in df_tf.to_dict('records'):
            if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr'] or cur['vol_ratio'] < 1.11:
                continue

            swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or \
                        (not pd.isna(cur.get('fvg_bull_zone')) and cur['low'] <= cur['fvg_bull_zone']) or \
                        cur['swept_htf_low'] or cur['is_spring']

            swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or \
                         (not pd.isna(cur.get('fvg_bear_zone')) and cur['high'] >= cur['fvg_bear_zone']) or \
                         cur['swept_htf_high'] or cur['is_utad']

            bull_ob = cur['bull_ob_zone']
            bear_ob = cur['bear_ob_zone']
            ob_mitigated_bull = (not pd.isna(bull_ob) and cur['low'] <= bull_ob)
            ob_mitigated_bear = (not pd.isna(bear_ob) and cur['high'] >= bear_ob)

            has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
            has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
            closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
            closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

            sig = "BUY" if ((swept_low or ob_mitigated_bull) and has_wick_buy and closed_high) else \
                  ("SELL" if ((swept_high or ob_mitigated_bear) and has_wick_sell and closed_low) else None)

            if sig:
                # Rebuilt: SL anchored beyond structural swing / buffer >= min_sl (Checklist #6)
                sl_dist = max(cur['atr'] * 1.5, min_sl)
                
                # Rebuilt Entry: 25% to 35% pullback into wick/FVG for high probability limit fill
                if sig == "BUY":
                    entry = round(cur['low'] + 0.35 * cur['lower_wick'], digits)
                    sl = round(entry - sl_dist, digits)
                    risk = entry - sl
                else:
                    entry = round(cur['high'] - 0.35 * cur['upper_wick'], digits)
                    sl = round(entry + sl_dist, digits)
                    risk = sl - entry

                if risk >= min_sl:
                    setup_time = int(cur['time']) + 300
                    setups.append({
                        "time": setup_time,
                        "signal": sig,
                        "entry": entry,
                        "sl": sl,
                        "risk": risk,
                        "atr": cur['atr'],
                        "tf": tf,
                        "bar_duration": 300
                    })

    return sorted(setups, key=lambda x: x['time'])

def main():
    if not mt5.initialize():
        print("MT5 init failed")
        return
        
    days = 30
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=days)
    
    symbols = ["XAUUSDm", "XAGUSDm"]
    all_syms = [s.name for s in mt5.symbols_get()]
    actual_syms = [s for s in ["XAUUSDm", "XAGUSDm", "XAUUSD.iux", "XAGUSD.iux"] if s in all_syms][:2]
    
    print(f"Testing Rebuilt S20.304 across: {actual_syms} (30 days)...")
    
    timeframes = ['M1','M5','M15','M30','H1']
    data = {}
    for sym in actual_syms:
        rates_by_tf = {}
        for tf in timeframes:
            r = mt5.copy_rates_range(sym, getattr(mt5, f"TIMEFRAME_{tf}"), start_dt, now)
            if r is not None and len(r) > 0:
                rates_by_tf[tf] = r
                
        dfs = {tf: compute_marathon_300_synergies(r) for tf, r in rates_by_tf.items()}
        digits = 2 if "XAU" in sym else 3
        point = 0.01 if "XAU" in sym else 0.001
        
        m5_rates = rates_by_tf.get('M5')
        m1_rates = rates_by_tf.get('M1')
        m5_times = [int(r['time']) for r in m5_rates] if m5_rates is not None else []
        m1_times = [int(r['time']) for r in m1_rates] if m1_rates is not None else []
        
        data[sym] = {
            "dfs": dfs,
            "digits": digits,
            "point": point,
            "m5_bars": m5_rates,
            "m5_times": m5_times,
            "m1_bars": m1_rates,
            "m1_times": m1_times,
            "spread": 0.15 if "XAU" in sym else 0.015,
            "penetration": 0.05 if "XAU" in sym else 0.005,
            "slippage": 0.05 if "XAU" in sym else 0.005,
        }
        
    mt5.shutdown()
    
    print("\n" + "="*95)
    print(" 🛠️ REBUILDING S20.304: GRID SEARCH FOR QUANT COMPLIANCE (MIN SL BUFFER)")
    print("="*95)
    
    for min_sl in [1.0, 1.5, 2.0, 2.5, 3.0]:
        combined_trades = []
        for sym in actual_syms:
            d = data[sym]
            setups = extract_rebuilt_setups(sym, d['dfs'], d['digits'], d['point'], min_sl_usd=min_sl)
            t = run_quant_simulation(
                sym, d['m5_bars'], d['m5_times'], d['m1_bars'], d['m1_times'], setups,
                spread_usd=d['spread'], penetration_usd=d['penetration'], sl_slippage_usd=d['slippage'],
                concurrent=True, max_concurrent=3
            )
            combined_trades.extend(t)
            
        combined_trades.sort(key=lambda x: x['fill_time'])
        title = f"Min SL ${min_sl:.2f} (Spread/SL < {d['spread']/min_sl*100:.1f}%)"
        print(summarize(title, combined_trades))
        
    print("="*95 + "\n")

if __name__ == "__main__":
    main()
