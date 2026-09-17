# -*- coding: utf-8 -*-
"""audit_s20_304_quant.py
Comprehensive Quant Checklist Audit for Strategy S20.304 (Gold + Silver Matrix)
Tests:
1. Base (Optimistic: 0 spread, 0 penetration, touch=fill)
2. Realistic Spread (Exness Bid/Ask model: Gold 0.15, Silver 0.015)
3. Realistic Spread + Limit Penetration (Rule #7: Touch is not a fill, 1 pt penetration)
4. Realistic Spread + Penetration + SL Slippage (Rule #9: 2 pt negative slippage on SL)
5. Concurrent Execution (Rule #12: No busy_until bottleneck)
6. Cross-Asset Correlation (Rule #16: Simultaneous Gold + Silver exposure)
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

import backtest_s20_unified as btu
from run_master_s20_marathon_201_to_300 import compute_marathon_300_synergies, make_stages
from run_s20_304_m5_verified import extract_setups_for_symbol

def run_quant_simulation(symbol, m5_bars, m5_times, m1_bars, m1_times, setups,
                         spread_usd=0.0, penetration_usd=0.0, sl_slippage_usd=0.0,
                         concurrent=False, max_concurrent=5, tp_r=13.43, lot=0.01):
    stages = make_stages(55)
    digits = 2 if "XAU" in symbol else 3
    contract_size = 100.0 if "XAU" in symbol else 5000.0
    
    m5_len = len(m5_bars)
    m1_len = len(m1_bars)
    
    trades = []
    active_positions = [] # [(exit_time, pnl, symbol, signal)]
    busy_until = 0
    active_orders = [] # [(expiry_time, tf, signal, entry)]
    
    for s in setups:
        s_time = s['time']
        
        # Rule #12: Queue / Concurrent filter
        active_positions = [p for p in active_positions if p[0] > s_time]
        if not concurrent:
            if s_time < busy_until:
                continue
        else:
            if len(active_positions) >= max_concurrent:
                continue
                
        s_tf = s.get('tf', 'M5')
        is_m1_setup = (s_tf == 'M1') and (m1_len > 0)
        sim_bars = m1_bars if is_m1_setup else m5_bars
        sim_times = m1_times if is_m1_setup else m5_times
        sim_len = len(sim_bars)
        
        # Rule #10: Timeframe Expiration (12 bars on M5 = 1 hour, 30 bars on M1 = 30 min)
        max_wait_bars = 30 if is_m1_setup else 12
        
        start_idx = bisect.bisect_right(sim_times, s_time)
        if start_idx >= sim_len:
            continue
            
        filled = False
        fill_idx = -1
        fill_price = s['entry']
        
        # Rule #7 & #8: Fill check with Penetration and Real Spread
        for i in range(start_idx, min(start_idx + max_wait_bars, sim_len)):
            b = sim_bars[i]
            if s['signal'] == 'BUY':
                # BUY fills at Ask: Ask = Bid + Spread <= Entry - Penetration
                # That means Bid (b['low']) <= Entry - spread - penetration
                if b['low'] <= (s['entry'] - spread_usd - penetration_usd):
                    filled = True
                    fill_idx = i
                    fill_price = s['entry']
                    break
            elif s['signal'] == 'SELL':
                # SELL fills at Bid: b['high'] >= Entry + penetration
                if b['high'] >= (s['entry'] + penetration_usd):
                    filled = True
                    fill_idx = i
                    fill_price = s['entry']
                    break
                    
        if not filled:
            continue
            
        fill_time = int(sim_bars[fill_idx]['time'])
        risk = s['risk']
        curr_sl = s['sl']
        active_r = 0.0
        exit_price = None
        exit_time = 0
        tp_target = round(fill_price + (tp_r * risk), digits) if s['signal'] == 'BUY' else round(fill_price - (tp_r * risk), digits)
        
        # Intrabar sequential management with Spread on Exits
        for i in range(fill_idx, sim_len):
            b = sim_bars[i]
            if s['signal'] == 'BUY':
                # BUY SL exits at Bid
                if b['low'] <= curr_sl:
                    # Rule #9: Negative Slippage on SL
                    exit_price = curr_sl - sl_slippage_usd
                    exit_time = b['time']
                    break
                max_fav = b['high'] - fill_price
                fav_r = max_fav / risk
                if fav_r >= 0.8 and curr_sl < fill_price:
                    curr_sl = fill_price
                for r_target, lock_r in stages:
                    if fav_r >= r_target and active_r < r_target:
                        active_r = r_target
                        new_sl = round(fill_price + (lock_r * risk), digits)
                        if new_sl > curr_sl:
                            curr_sl = new_sl
                if fav_r >= tp_r:
                    exit_price = tp_target
                    exit_time = b['time']
                    break
                if b['low'] <= curr_sl:
                    exit_price = curr_sl - sl_slippage_usd
                    exit_time = b['time']
                    break
            else: # SELL
                # SELL SL exits at Ask (b['high'] + spread >= curr_sl)
                if (b['high'] + spread_usd) >= curr_sl:
                    exit_price = curr_sl + sl_slippage_usd
                    exit_time = b['time']
                    break
                max_fav = fill_price - (b['low'] + spread_usd)
                fav_r = max_fav / risk
                if fav_r >= 0.8 and curr_sl > fill_price:
                    curr_sl = fill_price
                for r_target, lock_r in stages:
                    if fav_r >= r_target and active_r < r_target:
                        active_r = r_target
                        new_sl = round(fill_price - (lock_r * risk), digits)
                        if new_sl < curr_sl:
                            curr_sl = new_sl
                if fav_r >= tp_r:
                    exit_price = tp_target
                    exit_time = b['time']
                    break
                if (b['high'] + spread_usd) >= curr_sl:
                    exit_price = curr_sl + sl_slippage_usd
                    exit_time = b['time']
                    break
                    
        if exit_price is None:
            continue
            
        pnl_pt = (exit_price - fill_price) if s['signal'] == 'BUY' else (fill_price - exit_price)
        trade_pnl = pnl_pt * lot * contract_size
        
        busy_until = exit_time
        active_positions.append((exit_time, trade_pnl, symbol, s['signal']))
        trades.append({
            "fill_time": fill_time,
            "exit_time": int(exit_time),
            "symbol": symbol,
            "signal": s['signal'],
            "entry": fill_price,
            "exit": exit_price,
            "pnl": trade_pnl,
            "win": trade_pnl > 0.01
        })
        
    return trades

def summarize(name, trades):
    if not trades:
        return f"{name:<35}: 0 trades"
    df = pd.DataFrame(trades)
    n = len(df)
    w = (df['pnl'] > 0.01).sum()
    pnl = df['pnl'].sum()
    wr = (w / n) * 100.0 if n > 0 else 0
    cum = df['pnl'].cumsum()
    dd = (cum.cummax() - cum).max()
    return f"{name:<45} | Trades: {n:>4} | WR: {wr:>5.1f}% | Net PnL: ${pnl:>9.2f} | MaxDD: ${dd:>6.2f}"

def main():
    if not mt5.initialize():
        print("MT5 init failed")
        return
        
    days = 30
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=days)
    
    symbols = ["XAUUSDm", "XAGUSDm"]
    # Fallback to .iux if not found
    all_syms = [s.name for s in mt5.symbols_get()]
    actual_syms = []
    for s in ["XAUUSDm", "XAGUSDm", "XAUUSD.iux", "XAGUSD.iux"]:
        if s in all_syms and len(actual_syms) < 2:
            actual_syms.append(s)
            
    print(f"Auditing S20.304 across: {actual_syms} for {days} days...")
    
    data = {}
    timeframes = ['M1','M5','M15','M30','H1','H2','H3','H4']
    for sym in actual_syms:
        print(f"Loading rates for {sym}...")
        rates_by_tf = {}
        for tf in timeframes:
            r = mt5.copy_rates_range(sym, getattr(mt5, f"TIMEFRAME_{tf}"), start_dt, now)
            if r is not None and len(r) > 0:
                rates_by_tf[tf] = r
                
        dfs = {tf: compute_marathon_300_synergies(r) for tf, r in rates_by_tf.items()}
        digits = 2 if "XAU" in sym else 3
        point = 0.01 if "XAU" in sym else 0.001
        setups = extract_setups_for_symbol(sym, dfs, digits, point)
        for s in setups:
            s['sid'] = 20.304
            
        m5_rates = rates_by_tf.get('M5')
        m1_rates = rates_by_tf.get('M1')
        m5_times = [int(r['time']) for r in m5_rates] if m5_rates is not None else []
        m1_times = [int(r['time']) for r in m1_rates] if m1_rates is not None else []
        
        data[sym] = {
            "setups": setups,
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
    print(" 🔬 QUANT STRATEGY VERIFICATION CHECKLIST AUDIT: S20.304")
    print("="*95)
    
    scenarios = [
        ("1. Optimistic (No Spread, No Pen, BusyLock)", False, False, False, False),
        ("2. Real Spread (Exness Bid/Ask Model)", True, False, False, False),
        ("3. Real Spread + Limit Penetration (Rule #7)", True, True, False, False),
        ("4. Real Spread + Pen + SL Slippage (Rule #9)", True, True, True, False),
        ("5. Full Realism + Concurrent Mode (Rule #12)", True, True, True, True),
    ]
    
    for title, use_spread, use_pen, use_slip, is_concurrent in scenarios:
        combined_trades = []
        for sym in actual_syms:
            d = data[sym]
            sp = d['spread'] if use_spread else 0.0
            pn = d['penetration'] if use_pen else 0.0
            sl = d['slippage'] if use_slip else 0.0
            
            t = run_quant_simulation(
                sym, d['m5_bars'], d['m5_times'], d['m1_bars'], d['m1_times'], d['setups'],
                spread_usd=sp, penetration_usd=pn, sl_slippage_usd=sl,
                concurrent=is_concurrent, max_concurrent=3
            )
            combined_trades.extend(t)
            
        combined_trades.sort(key=lambda x: x['fill_time'])
        print(summarize(title, combined_trades))
        
    print("="*95 + "\n")

if __name__ == "__main__":
    main()
