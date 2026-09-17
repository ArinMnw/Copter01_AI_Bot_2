# -*- coding: utf-8 -*-
"""audit_all_11_s20_quant.py
Audit all 11 S20 Institutional strategies against the 19 Quant Verification Rules.
Compare:
1. Zero Spread & Zero Friction (As in current backtest_s20_unified.py)
2. Realistic Friction (Spread 0.15 on Gold / realistic on others, Penetration 0.05, SL Slippage 0.05, SL-First)
"""
import sys, os, bisect
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5

root_dir = r"d:\Project\Copter01_AI_Bot_2"
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, "strategy"))
sys.path.append(os.path.join(root_dir, "strategy", "s20.301"))
sys.path.append(os.path.join(root_dir, "strategy", "s20.304"))

import backtest_s20_unified as btu
from goal_s20_53_to_100 import init_mt5

def test_all_11_audit():
    if not init_mt5():
        print("MT5 init failed")
        return
    
    sym = "XAUUSDm"
    all_syms = [s.name for s in mt5.symbols_get()]
    if sym not in all_syms:
        sym = "XAUUSD.iux" if "XAUUSD.iux" in all_syms else all_syms[0]
        
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=60)
    
    r_m1 = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M1, start_dt, now)
    r_m5 = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M5, start_dt, now)
    r_m15 = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M15, start_dt, now)
    mt5.shutdown()
    
    rates_by_tf = {
        "M1": r_m1,
        "M5": r_m5,
        "M15": r_m15,
    }
    
    m5_times = [int(r['time']) for r in r_m5]
    m1_times = [int(r['time']) for r in r_m1]
    
    print("="*105)
    print(f" 📊 AUDIT ALL 11 S20 STRATEGIES ON {sym} (60-DAY EXNESS TICKS/BARS)")
    print("="*105)
    print(f"{'Strategy':<30} | {'Zero Friction PnL':<18} | {'Real Friction PnL':<18} | {'Trades':<8} | {'Status'}")
    print("-" * 105)
    
    for sid_float in btu.ALL_SIDS:
        sname = f"S{sid_float}"
        try:
            setups = btu.extract_setups_for_strategy(sid_float, sym, rates_by_tf, 2, 0.01)
            if not setups:
                print(f"{sname:<30} | No setups found")
                continue
                
            # 1. Zero friction
            t_zero = btu.simulate_strategy_trades(
                sid_float, sym, r_m5, m5_times, setups, 0.01, 100, 2,
                concurrent=True, m1_bars=r_m1, m1_times=m1_times
            )
            pnl_zero = sum(t['pnl_usd'] for t in t_zero) if t_zero else 0.0
            
            # 2. Realistic Friction (Spread = 0.15 USD, Penetration = 0.05 USD, SL Slippage = 0.05 USD)
            # We simulate with penetration and spread
            spread = 0.15
            penetration = 0.05
            slippage = 0.05
            
            t_real = []
            for s in setups:
                s_time = s['time']
                s_tf = s.get('tf', 'M5')
                is_m1 = (s_tf == 'M1')
                sim_bars = r_m1 if is_m1 else r_m5
                sim_times = m1_times if is_m1 else m5_times
                sim_len = len(sim_bars)
                max_wait = 60 if is_m1 else 12
                
                start_idx = bisect.bisect_right(sim_times, s_time)
                if start_idx >= sim_len:
                    continue
                
                # Penetration fill check (Rule #7)
                filled = False
                fill_idx = -1
                for i in range(start_idx, min(start_idx + max_wait, sim_len)):
                    b = sim_bars[i]
                    if s['signal'] == 'BUY' and b['low'] <= (s['entry'] - penetration):
                        filled = True
                        fill_idx = i
                        break
                    elif s['signal'] == 'SELL' and b['high'] >= (s['entry'] + penetration):
                        filled = True
                        fill_idx = i
                        break
                if not filled:
                    continue
                
                is_smc = sid_float in (20.301, 20.302, 20.303, 20.304)
                tp_r = 13.45 if sid_float == 20.303 else 13.43
                risk = s['risk']
                tp_price = s.get('tp') if not is_smc else (round(fill_price + (tp_r * risk), 2) if s['signal'] == 'BUY' else round(fill_price - (tp_r * risk), 2))
                
                # Exit evaluation starting from next bar or post-fill close (Rule #5)
                exit_price = None
                for i in range(fill_idx + 1, sim_len):
                    b = sim_bars[i]
                    if s['signal'] == 'BUY':
                        # SL check first (Rule #4) with slippage (Rule #9)
                        if b['low'] <= sl_price:
                            exit_price = sl_price - slippage
                            break
                        # TP check with spread (Rule #8)
                        if b['high'] >= (tp_price + spread):
                            exit_price = tp_price
                            break
                    else: # SELL
                        if b['high'] >= (sl_price + spread):
                            exit_price = sl_price + spread + slippage
                            break
                        if b['low'] <= tp_price:
                            exit_price = tp_price
                            break
                
                if exit_price is not None:
                    pnl = (exit_price - fill_price) if s['signal'] == 'BUY' else (fill_price - exit_price)
                    t_real.append(pnl * 0.01 * 100)
            
            pnl_real = sum(t_real)
            diff = pnl_real - pnl_zero
            status = "✅ ROBUST" if pnl_real > 0 else ("⚠️ SPREAD FRAGILE" if pnl_zero > 0 else "❌ UNPROFITABLE")
            
            print(f"{sname:<30} | ${pnl_zero:>10.2f}        | ${pnl_real:>10.2f}        | {len(setups):<8} | {status}")
            
        except Exception as e:
            print(f"{sname:<30} | Error: {e}")
            
    print("="*105 + "\n")

if __name__ == "__main__":
    test_all_11_audit()
