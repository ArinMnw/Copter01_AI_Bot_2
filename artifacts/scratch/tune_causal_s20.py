import os
import sys
import json
import importlib
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
strategy_dir = os.path.join(root_dir, "strategy")
if root_dir not in sys.path: sys.path.insert(0, root_dir)
if strategy_dir not in sys.path: sys.path.insert(0, strategy_dir)

import config
import backtest_s20_unified as btu
from run_s20_304_m5_verified import ALL_SYMBOLS, DEFAULT_SYMBOL_WEIGHTS, init_mt5

def tune_s20_304():
    print("=== Tuning S20.304 under Causal Execution ===", flush=True)
    if not init_mt5():
        print("Failed to init MT5")
        return

    # Load rates once
    print("Loading rates for 365 days...", flush=True)
    bkk_tz = timezone(timedelta(hours=7))
    end_dt = datetime.now(bkk_tz)
    start_dt = end_dt - timedelta(days=365)
    tfs = ['H4', 'H3', 'H2', 'H1', 'M30', 'M20', 'M15', 'M12', 'M5', 'M1']
    
    rates_all = {}
    for sym in ALL_SYMBOLS:
        rates_by_tf = {}
        for tf in tfs:
            tf_const = getattr(mt5, f"TIMEFRAME_{tf}", None)
            if tf_const is not None:
                r = mt5.copy_rates_range(sym, tf_const, start_dt, end_dt)
                if r is None or len(r) == 0:
                    count = 65000 if tf == "M1" else 75000
                    r = mt5.copy_rates_from_pos(sym, tf_const, 0, count)
                if r is not None and len(r) > 0:
                    rates_by_tf[tf] = r
        rates_all[sym] = rates_by_tf
        print(f"Loaded {sym} (TFs: {len(rates_by_tf)})", flush=True)
    
    best_res = None
    best_pnl = -999999
    
    # Grid search parameters
    depths = [0.0, 0.05, 0.10, 0.12, 0.15, 0.20, 0.25, 0.35, 0.50, 0.75, 1.00]
    sl_mults = [0.15, 0.20, 0.30, 0.40, 0.50]
    tp_rs = [1.2, 1.5, 1.8, 2.0, 2.5, 3.0, 4.0, 5.0, 8.0, 13.43]
    
    for d in depths:
        for sl_m in sl_mults:
            for tp_r in tp_rs:
                tune_params = {
                    "active_depth": d,
                    "sl_mult": sl_m,
                    "tp_r": tp_r
                }
                os.environ["S20_ENTRY_TUNE_PARAMS"] = json.dumps(tune_params)
                
                try:
                    import run_s20_304_m5_verified as r304
                    importlib.reload(r304)
                    
                    tot_pnl = 0
                    tot_trades = 0
                    tot_wins = 0
                    
                    for sym in ALL_SYMBOLS:
                        if sym not in rates_all or not rates_all[sym]: continue
                        sinfo = mt5.symbol_info(sym)
                        digits = sinfo.digits if sinfo else 2
                        point = sinfo.point if sinfo else 0.01
                        
                        dfs = {tf: r304.compute_marathon_300_synergies(r) for tf, r in rates_all[sym].items()}
                        raw_setups = r304.extract_setups_for_symbol(sym, dfs, digits, point)
                        for s in raw_setups:
                            s["sid"] = 20.304
                            s["tp"] = round(s["entry"] + tp_r * s["risk"], digits) if s["signal"] == "BUY" else round(s["entry"] - tp_r * s["risk"], digits)
                        
                        # Helper functions in backtest_s20_unified module directly
                        m5_bars = [dict(r) for r in rates_all[sym]["M5"]] if "M5" in rates_all[sym] else []
                        m5_times = [int(r["time"]) for r in rates_all[sym]["M5"]] if "M5" in rates_all[sym] else []
                        m1_bars = [dict(r) for r in rates_all[sym]["M1"]] if "M1" in rates_all[sym] else []
                        m1_times = [int(r["time"]) for r in rates_all[sym]["M1"]] if "M1" in rates_all[sym] else []
                        
                        lot = 0.01 * DEFAULT_SYMBOL_WEIGHTS.get(sym, 1.0)
                        sym_spread = 0.26 if "XAU" in sym else (0.03 if "XAG" in sym else (0.010 if "JPY" in sym else 0.00010))
                        
                        tr, pnl, w, l, be = btu.simulate_strategy_trades(
                            20.304, sym, m5_bars, m5_times, raw_setups, lot, 100, digits,
                            m1_bars=m1_bars, m1_times=m1_times, sym_spread=sym_spread
                        )
                        tot_pnl += pnl
                        tot_trades += tr
                        tot_wins += w
                    
                    wr = (tot_wins / tot_trades * 100) if tot_trades > 0 else 0
                    if tot_pnl > best_pnl:
                        best_pnl = tot_pnl
                        best_res = (d, sl_m, tp_r, tot_trades, wr, tot_pnl)
                        print(f"👉 NEW BEST: depth={d}, sl_m={sl_m}, tp_r={tp_r} -> Trades={tot_trades}, WR={wr:.1f}%, PnL=+${tot_pnl:,.2f}", flush=True)
                except Exception as e:
                    print(f"Err: {e}", flush=True)

if __name__ == "__main__":
    tune_s20_304()
