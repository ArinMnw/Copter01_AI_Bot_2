import re
import csv
import numpy as np
import MetaTrader5 as mt5
import itertools
from collections import defaultdict
import config
import sim_s30_backtest as s30sim
from optimize_s88_allin4s_fast import _make_s84, _make_s86, _grid_s84, _grid_s86, TF_EXTRA_BARS, OVERLAY_CFG
from sim_s84_backtest import run_single as run_s84
from sim_s86_backtest import run_single as run_s86
from sim_s62_backtest import _atr_series
from optimize_s72_vs_demo_portfolio import DEFAULT_SPREAD
from optimize_s75_champion_formula import _simulate_leg
from ambfix_sweep2 import _post_filter_raw, _invert_raw

def parse_log(max_legs=None):
    legs = []
    # Log format:
    # - AF890 = AF889 + DIRECT_S84c4369_RD2.7-3.4_H12x600.0 -> avg: 10002.71, min: 10002.71
    pattern = re.compile(r"^\- AF\d+ = AF\d+ \+ (DIRECT|INVERSE)_S(\d+)c(\d+)_RD([a-zA-Z0-9.\-]+)_H(\d+)x([0-9.]+)")
    with open("lts_auto_ladder_log.md", "r", encoding="utf-8") as f:
        for line in f:
            m = pattern.match(line.strip())
            if m:
                mode = m.group(1).lower()
                fam = f"s{m.group(2)}"
                cfg_idx = int(m.group(3))
                band = m.group(4)
                hour = int(m.group(5))
                weight = float(m.group(6))
                label = f"{mode.upper()}_S{m.group(2)}c{cfg_idx}_RD{band}_H{hour}"
                legs.append({
                    "label": label,
                    "fam": fam,
                    "cfg_idx": cfg_idx,
                    "mode": mode,
                    "band": band,
                    "hour": hour,
                    "weight": weight
                })
            if max_legs and len(legs) >= max_legs:
                break
    return legs

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-legs", type=int, default=None, help="Limit number of legs to parse")
    args = parser.parse_args()
    
    legs = parse_log(max_legs=args.max_legs)
    print(f"Parsed {len(legs)} legs from log.")
    
    unique_bases = set((leg["fam"], leg["cfg_idx"]) for leg in legs)
    print(f"Unique base configs needed: {len(unique_bases)}")
    
    if not config.mt5_initialize(mt5):
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
        
    days = 550
    raw_trades_cache = {}
    
    try:
        for fam, cfg_idx in unique_bases:
            print(f"Running base config {fam}c{cfg_idx}...")
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
            
            raw = runner(bars, run_cfg, days, DEFAULT_SPREAD)
            raw_trades_cache[(fam, cfg_idx)] = raw
    finally:
        mt5.shutdown()
        
    print("Reconstructing daily PnL vectors...")
    dates = []
    
    # Load dates from base empty CSV to ensure alignment
    with open("lts0_empty_daily.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row["days"]) == 550:
                dates.append(row["date"])
                
    dates_set = set(dates)
    dates_idx = {d: i for i, d in enumerate(dates)}
    
    P_matrix = np.zeros((len(dates), len(legs)), dtype=float)
    W_orig = np.zeros(len(legs), dtype=float)
    leg_labels = []
    
    for j, leg in enumerate(legs):
        raw = raw_trades_cache[(leg["fam"], leg["cfg_idx"])]
        filtered_raw = _post_filter_raw(raw, leg["band"], leg["hour"])
        if leg["mode"] == "inverse":
            filtered_raw = _invert_raw(filtered_raw)
            
        _twp, _eq, by_day = _simulate_leg(filtered_raw, OVERLAY_CFG)
        
        for d, pnl in by_day.items():
            if d in dates_idx:
                P_matrix[dates_idx[d], j] = float(pnl)
                
        W_orig[j] = leg["weight"]
        leg_labels.append(leg["label"])
        
    np.save("lts_P_matrix.npy", P_matrix)
    np.save("lts_W_orig.npy", W_orig)
    
    import json
    with open("lts_leg_labels.json", "w") as f:
        json.dump(leg_labels, f)
        
    print("Matrix P saved. Shape:", P_matrix.shape)
    
    # Verify reconstruction
    final_pnl = P_matrix @ W_orig
    print(f"Reconstructed Avg $/day: {final_pnl.mean():.2f}")
    print(f"Reconstructed Worst day: {final_pnl.min():.2f}")

if __name__ == "__main__":
    main()
