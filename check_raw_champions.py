import argparse
import itertools
import MetaTrader5 as mt5
import numpy as np

import config
import sim_s30_backtest as s30sim
from optimize_s88_allin4s_fast import _make_s84, _make_s86, _grid_s84, _grid_s86, TF_EXTRA_BARS
from sim_s84_backtest import run_single as run_s84
from sim_s86_backtest import run_single as run_s86
from sim_s62_backtest import _atr_series
from optimize_s72_vs_demo_portfolio import DEFAULT_SPREAD

def main():
    if not config.mt5_initialize(mt5):
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
        
    days = 550
    champions = [
        ("s84", 28, "S84 Target28 (Classic)"),
        ("s84", 6017, "c6017 (AF22 base)"),
        ("s84", 889, "c889 (AF34 base)"),
        ("s84", 3057, "c3057 (Strong M15)"),
        ("s84", 4369, "c4369 (Another S84)"),
        ("s84", 5505, "c5505 (Another S84)"),
        ("s86", 7171, "s86c7171 (AF47 base, Clean)"),
        ("s86", 7187, "s86c7187"),
        ("s86", 11, "s86c11 (Recent LTS favorite)")
    ]
    
    results = []
    
    try:
        for fam, cfg_idx, name in champions:
            grid = _grid_s84("micro") if fam == "s84" else _grid_s86("micro")
            all_vals = list(itertools.product(*grid))
            cfg_vals = all_vals[cfg_idx]
            
            maker = _make_s84 if fam == "s84" else _make_s86
            runner = run_s84 if fam == "s84" else run_s86
            cfg = maker(cfg_vals)
            tf = cfg["ENTRY_TF"]
            
            bars = s30sim.fetch_bars(config.SYMBOL, tf, days, extra_bars=TF_EXTRA_BARS.get(tf, 700))
            
            run_cfg = dict(cfg)
            run_cfg["_ATR14"] = _atr_series(bars, 14)
            run_cfg["_DT_BKK"] = [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]
            
            raw_trades = runner(bars, run_cfg, days, DEFAULT_SPREAD)
            
            from optimize_s75_champion_formula import _simulate_leg
            from optimize_s88_allin4s_fast import OVERLAY_CFG
            
            _twp, _eq, by_day = _simulate_leg(raw_trades, OVERLAY_CFG)
            
            # calculate raw PnL
            total_profit = 0.0
            total_loss = 0.0
            gross_profit = 0.0
            gross_loss = 0.0
            
            for d, pnl in by_day.items():
                if pnl > 0:
                    gross_profit += pnl
                else:
                    gross_loss += abs(pnl)
                total_profit += pnl
                
            pf = gross_profit / gross_loss if gross_loss > 0 else 999.0
            avg_day = total_profit / days
            
            results.append({
                "name": name,
                "trades": len(raw_trades),
                "total_pnl": total_profit,
                "avg_day": avg_day,
                "pf": pf
            })
            
    finally:
        mt5.shutdown()
        
    # Sort by total_pnl descending
    results.sort(key=lambda x: x["total_pnl"], reverse=True)
    
    print("\n--- RAW PERFORMANCE (550 DAYS, W=1) ---")
    for r in results:
        print(f"{r['name']:<30} | Trades: {r['trades']:<4} | Avg $/day: {r['avg_day']:>6.2f} | PF: {r['pf']:>5.2f} | Total PnL: {r['total_pnl']:>8.2f}")

if __name__ == "__main__":
    main()
