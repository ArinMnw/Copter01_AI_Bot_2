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

def test_entry_modes():
    print("=== Testing Market Entry vs Limit Retest for S20.304 ===", flush=True)
    if not init_mt5():
        print("Failed to init MT5")
        return

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

    import run_s20_304_m5_verified as r304
    
    for mode_name, depth in [("Market (Bar Close)", 1.0), ("Shallow Retest (0.85)", 0.85), ("Mid Retest (0.50)", 0.50), ("Deep Retest (0.35)", 0.35)]:
        tune_params = {"active_depth": depth, "sl_mult": 0.30, "tp_r": 1.8}
        os.environ["S20_ENTRY_TUNE_PARAMS"] = json.dumps(tune_params)
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
            
            m5_bars = rates_all[sym]["M5"] if "M5" in rates_all[sym] else []
            m5_times = [int(r["time"]) for r in rates_all[sym]["M5"]] if "M5" in rates_all[sym] else []
            m1_bars = rates_all[sym].get("M1")
            m1_times = [int(r["time"]) for r in rates_all[sym]["M1"]] if "M1" in rates_all[sym] else []
            
            lot = 0.01 * DEFAULT_SYMBOL_WEIGHTS.get(sym, 1.0)
            sym_spread = 0.26 if "XAU" in sym else (0.03 if "XAG" in sym else (0.010 if "JPY" in sym else 0.00010))
            
            trades = btu.simulate_strategy_trades(
                20.304, sym, m5_bars, m5_times, raw_setups, lot, 100, digits,
                m1_bars=m1_bars, m1_times=m1_times, sym_spread=sym_spread
            )
            tot_trades += len(trades)
            tot_pnl += sum(t.get("pnl_usd", 0.0) for t in trades)
            tot_wins += len([t for t in trades if t.get("pnl_usd", 0.0) > 0.01])
            
        wr = (tot_wins / tot_trades * 100) if tot_trades > 0 else 0
        print(f"[{mode_name}] Trades={tot_trades}, Wins={tot_wins}, WR={wr:.1f}%, Net PnL=+${tot_pnl:,.2f}", flush=True)

if __name__ == "__main__":
    test_entry_modes()
