# -*- coding: utf-8 -*-
import os
import sys
import time
import argparse
import importlib.util
from datetime import datetime, timedelta, timezone
import MetaTrader5 as mt5
import pandas as pd
import numpy as np

import sys
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from goal_s20_53_to_100 import init_mt5, compute_indicators, run_simulation

def main():
    if not init_mt5():
        return
        
    BKK = timezone(timedelta(hours=7))
    end_time = datetime.now(BKK)
    start_time = end_time - timedelta(days=365)
    
    tfs = {
        'M1': mt5.TIMEFRAME_M1,
        'M5': mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15,
        'M30': mt5.TIMEFRAME_M30,
        'H1': mt5.TIMEFRAME_H1,
        'H4': mt5.TIMEFRAME_H4,
        'D1': mt5.TIMEFRAME_D1
    }
    
    data_cache = {}
    for tf_name, tf_val in tfs.items():
        print(f"Fetching {tf_name}...")
        rates = mt5.copy_rates_range("XAUUSD.iux", tf_val, start_time, end_time)
        if rates is None or len(rates) == 0:
            rates = mt5.copy_rates_from_pos("XAUUSD.iux", tf_val, 0, 75000)
        
        if rates is not None and len(rates) > 0:
            df = compute_indicators(rates)
            data_cache[tf_name] = {
                'bars': df.to_dict('records'),
                'times': df['time'].values,
                'df': df
            }
            print(f"Loaded {len(rates)} bars for {tf_name}")
        else:
            print(f"Failed to load {tf_name}")
            data_cache[tf_name] = None
            
    base_dir = os.path.dirname(__file__)
    
    results = []
    
    for current_ver in range(55, 130):
        ver_dir = os.path.join(base_dir, f"s20.{current_ver}")
        strat_file = os.path.join(ver_dir, f"strategy20_{current_ver}.py")
        
        if not os.path.exists(strat_file):
            continue
            
        spec = importlib.util.spec_from_file_location(f"stg20_{current_ver}", strat_file)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        
        extract_func = getattr(module, f"extract_setups_s20_{current_ver}")
        
        # tp_r was generated dynamically in run_goal_55_to_129_real.py
        # It was tp_r = 5.50 + (i * 0.10) where i = current_ver - 55
        i = current_ver - 55
        tp_r = 5.50 + (i * 0.10)
        
        strat_results = {}
        
        for tf_name in tfs.keys():
            if not data_cache.get(tf_name):
                continue
                
            df = data_cache[tf_name]['df']
            bars = data_cache[tf_name]['bars']
            times = data_cache[tf_name]['times']
            
            setups = extract_func(df)
            res = run_simulation(bars, times, setups, tp_r=tp_r, stages=[])
            strat_results[tf_name] = res
            
        print(f"S20.{current_ver} evaluated on all TFs")
        results.append((current_ver, strat_results))
        
    # Write Markdown
    outpath = os.path.join(base_dir, "backtest-summary", "S20_55_to_129_365_day.md")
    
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write("# สรุป Backtest S20.55 – S20.129 (365 วัน ทุก Timeframe)\n\n")
        f.write("- Symbol: XAUUSD (Exness `XAUUSDm`) lot 0.01 | ช่วง BKK 1 ปีล่าสุด\n")
        f.write("- ต้นทุน: spread จริงของ symbol, swap, SL slippage 0.10\n")
        f.write("- ✅ = กลยุทธ์ทำกำไรสุทธิเป็นบวก\n\n")
        
        f.write("## ตารางสรุปรวมทุก Timeframe\n\n")
        
        # Header
        f.write("| S20 | TF | Trades | WR% | PnL ($) | Max DD ($) | สถานะ |\n")
        f.write("|---|---|---:|---:|---:|---:|---|\n")
        
        profitable = []
        
        for current_ver, strat_results in results:
            for tf_name in tfs.keys():
                if tf_name not in strat_results:
                    continue
                res = strat_results[tf_name]
                pnl = res['pnl']
                wr = res['wr']
                dd = res['max_dd']
                trades = res['trades']
                
                if trades == 0:
                    continue
                
                pnl_str = f"+{pnl:,.2f}" if pnl > 0 else f"{pnl:,.2f}"
                status = '✅ PASS' if pnl > 0 else '❌ FAIL'
                f.write(f"| {current_ver} | {tf_name} | {trades} | {wr:.1f} | {pnl_str} | {dd:,.2f} | {status} |\n")
                
                if pnl > 0:
                    profitable.append((current_ver, tf_name, trades, wr, pnl, dd))
                    
        f.write("\n## ตารางสรุปเฉพาะกลยุทธ์ที่ได้กำไร (Net Profit > 0)\n\n")
        
        if not profitable:
            f.write("> ⚠️ **ยังไม่มีกลยุทธ์ที่ทำกำไร (Net Profit > 0)**\n\n")
            f.write("| S20 | TF | Trades | WR% | PnL ($) | Max DD ($) | สถานะ |\n")
            f.write("|---|---|---:|---:|---:|---:|---|\n")
            f.write("| - | - | - | - | - | - | - |\n")
        else:
            f.write("| S20 | TF | Trades | WR% | PnL ($) | Max DD ($) | สถานะ |\n")
            f.write("|---|---|---:|---:|---:|---:|---|\n")
            profitable.sort(key=lambda x: x[4], reverse=True) # Sort by PnL desc
            
            for current_ver, tf_name, trades, wr, pnl, dd in profitable:
                pnl_str = f"+{pnl:,.2f}"
                f.write(f"| {current_ver} | {tf_name} | {trades} | {wr:.1f} | {pnl_str} | {dd:,.2f} | ✅ PASS |\n")
                
    print(f"Summary written to {outpath}")

if __name__ == "__main__":
    main()
