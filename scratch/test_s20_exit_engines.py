# -*- coding: utf-8 -*-
"""test_s20_exit_engines.py
Comparing Exit Engines for S20 setups under Realistic Exness Spread + Limit Penetration:
1. S20.304 Original 55-Stage Micro Ratchet
2. Clean Fixed RR (1:2, 1:2.5, 1:3) with BE @ 1R
3. ATR Trailing (Chandelier 2x ATR)
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
from test_rebuild_s20_304 import extract_rebuilt_setups

def run_exit_engine_sim(symbol, m5_bars, m5_times, setups, engine_type="fixed_rr",
                        target_rr=2.0, be_r=1.0, spread=0.15, penetration=0.05, slippage=0.05, lot=0.01):
    contract_size = 100.0 if "XAU" in symbol else 5000.0
    digits = 2 if "XAU" in symbol else 3
    m5_len = len(m5_bars)
    
    trades = []
    active_positions = []
    
    for s in setups:
        s_time = s['time']
        active_positions = [p for p in active_positions if p[0] > s_time]
        if len(active_positions) >= 2:
            continue
            
        start_idx = bisect.bisect_right(m5_times, s_time)
        if start_idx >= m5_len:
            continue
            
        filled = False
        fill_idx = -1
        fill_price = s['entry']
        
        # 12 M5 bars wait
        for i in range(start_idx, min(start_idx + 12, m5_len)):
            b = m5_bars[i]
            if s['signal'] == 'BUY':
                if b['low'] <= (s['entry'] - spread - penetration):
                    filled = True
                    fill_idx = i
                    break
            else:
                if b['high'] >= (s['entry'] + penetration):
                    filled = True
                    fill_idx = i
                    break
        if not filled:
            continue
            
        risk = s['risk']
        curr_sl = s['sl']
        tp_target = round(fill_price + (target_rr * risk), digits) if s['signal'] == 'BUY' else round(fill_price - (target_rr * risk), digits)
        exit_price = None
        exit_time = 0
        
        for i in range(fill_idx, m5_len):
            b = m5_bars[i]
            if s['signal'] == 'BUY':
                # SL check at Bid
                if b['low'] <= curr_sl:
                    exit_price = curr_sl - slippage
                    exit_time = b['time']
                    break
                # TP check at Bid
                if b['high'] >= tp_target:
                    exit_price = tp_target
                    exit_time = b['time']
                    break
                # BE logic
                if (b['high'] - fill_price) >= (be_r * risk) and curr_sl < fill_price:
                    curr_sl = fill_price + 0.10 # cover commission/spread
            else:
                # SL check at Ask
                if (b['high'] + spread) >= curr_sl:
                    exit_price = curr_sl + slippage
                    exit_time = b['time']
                    break
                # TP check at Ask
                if (b['low'] + spread) <= tp_target:
                    exit_price = tp_target
                    exit_time = b['time']
                    break
                # BE logic
                if (fill_price - (b['low'] + spread)) >= (be_r * risk) and curr_sl > fill_price:
                    curr_sl = fill_price - 0.10
                    
        if exit_price is None:
            continue
            
        pnl_pt = (exit_price - fill_price) if s['signal'] == 'BUY' else (fill_price - exit_price)
        trade_pnl = pnl_pt * lot * contract_size
        
        active_positions.append((exit_time, trade_pnl))
        trades.append({
            "fill_time": int(m5_bars[fill_idx]['time']),
            "exit_time": int(exit_time),
            "pnl": trade_pnl
        })
        
    return trades

def summarize_df(title, trades):
    if not trades:
        return f"{title:<40}: 0 trades"
    df = pd.DataFrame(trades)
    n = len(df)
    w = (df['pnl'] > 0.01).sum()
    pnl = df['pnl'].sum()
    wr = (w / n) * 100.0 if n > 0 else 0
    cum = df['pnl'].cumsum()
    dd = (cum.cummax() - cum).max()
    return f"{title:<40} | Trades: {n:>4} | WR: {wr:>5.1f}% | Net PnL: ${pnl:>8.2f} | MaxDD: ${dd:>6.2f}"

def main():
    from goal_s20_53_to_100 import init_mt5
    if not init_mt5():
        print("MT5 init failed")
        return
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=30)
    
    sym = "XAUUSDm"
    all_syms = [s.name for s in mt5.symbols_get()]
    if sym not in all_syms:
        sym = "XAUUSD.iux" if "XAUUSD.iux" in all_syms else all_syms[0]
        
    r_gold = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M5, start_dt, now)
    mt5.shutdown()
    if r_gold is None or len(r_gold) == 0:
        print(f"Failed to fetch rates for {sym}")
        return
        
    df_m5 = compute_marathon_300_synergies(r_gold)
    m5_times = [int(r['time']) for r in r_gold]
    
    print("\n" + "="*90)
    print(" 🎯 COMPARING EXIT ENGINES FOR GOLD WITH REALISTIC SPREAD & PENETRATION")
    print("="*90)
    
    # Extract setups with Min SL $2.0
    setups = extract_rebuilt_setups("XAUUSDm", {"M5": df_m5}, 2, 0.01, min_sl_usd=2.0)
    
    for rr in [1.5, 2.0, 2.5, 3.0, 4.0]:
        t = run_exit_engine_sim("XAUUSDm", r_gold, m5_times, setups, target_rr=rr, be_r=1.0)
        print(summarize_df(f"Clean Fixed 1:{rr} (BE @ 1R)", t))
        
    print("="*90 + "\n")

if __name__ == "__main__":
    main()
