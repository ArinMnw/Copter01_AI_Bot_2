import re
import csv
import numpy as np
import MetaTrader5 as mt5
import itertools
from collections import defaultdict
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

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
    with open(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'lts_auto_ladder_log.md'), "r", encoding="utf-8") as f:
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
    parser = argparse.ArgumentParser(description="Reconstruct LTS daily PnL vectors with exact weight mapping.")
    parser.add_argument("--max-legs", type=int, default=0, help="Max legs to include (0 for all)")
    parser.add_argument("--days", type=int, default=550, help="Number of recent days to reconstruct (default: 550)")
    parser.add_argument("--balance", type=float, default=None, help="Starting balance for CSV export")
    parser.add_argument("--weights", type=str, default=None, help="Path to optimized weights file (e.g. lts44_optimized_weights.txt)")
    args = parser.parse_args()
    
    all_legs = parse_log(max_legs=None) # Always parse all to get unique configs
    
    unique_configs = {}
    for leg in all_legs:
        if leg["label"] not in unique_configs:
            unique_configs[leg["label"]] = leg
            
    legs = []
    
    if args.weights and os.path.exists(args.weights):
        with open(args.weights, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(":")
                if len(parts) == 2:
                    label = parts[0].strip()
                    weight = float(parts[1].strip())
                    if label in unique_configs:
                        leg = dict(unique_configs[label])
                        leg["weight"] = weight
                        legs.append(leg)
        print(f"Loaded {len(legs)} optimized legs from {args.weights}")
    else:
        legs = all_legs[:args.max_legs] if args.max_legs > 0 else all_legs
        print(f"Parsed {len(legs)} legs from log (RAW weights).")
    
    unique_bases = set((leg["fam"], leg["cfg_idx"]) for leg in legs)
    print(f"Unique base configs needed: {len(unique_bases)}")
    
    if not config.mt5_initialize(mt5):
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
        
    days = args.days
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
    csv_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'lts0_empty_daily.csv')
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row["days"]) == 550:
                dates.append(row["date"])
                
    dates_set = set(dates)
    dates_idx = {d: i for i, d in enumerate(dates)}
    
    P_matrix = np.zeros((len(dates), len(legs)), dtype=float)
    W_orig = np.zeros(len(legs), dtype=float)
    leg_labels = []
    
    all_portfolio_trades = []
    
    for j, leg in enumerate(legs):
        raw = raw_trades_cache[(leg["fam"], leg["cfg_idx"])]
        filtered_raw = _post_filter_raw(raw, leg["band"], leg["hour"])
        if leg["mode"] == "inverse":
            filtered_raw = _invert_raw(filtered_raw)
            
        _twp, _eq, by_day = _simulate_leg(filtered_raw, OVERLAY_CFG)
        
        # Determine TF
        maker = _make_s84 if leg["fam"] == "s84" else _make_s86
        grid = _grid_s84("micro") if leg["fam"] == "s84" else _grid_s86("micro")
        all_vals = list(itertools.product(*grid))
        cfg_vals = all_vals[leg["cfg_idx"]]
        tf = maker(cfg_vals)["ENTRY_TF"]
        
        for t in _twp:
            t_scaled = dict(t)
            t_scaled["lts_leg"] = leg["label"]
            t_scaled["tf"] = tf
            t_scaled["lot_scaled"] = t["lot"] * leg["weight"]
            t_scaled["pnl_usd_scaled"] = t["pnl_usd"] * leg["weight"]
            all_portfolio_trades.append(t_scaled)
        
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
    
    # Export chronological CSV
    print(f"Exporting {len(all_portfolio_trades)} simulated orders to CSV...")
    all_portfolio_trades.sort(key=lambda x: x["fill_time_ts"])
    
    # Auto-adjust starting balance if not explicitly provided
    if args.balance is not None:
        START_BALANCE = args.balance
    else:
        START_BALANCE = 1000.0 if len(legs) <= 100 else 10000.0
    
    running_balance = START_BALANCE
    csv_rows = []
    
    for t in all_portfolio_trades:
        running_balance += t["pnl_usd_scaled"]
        
        # Format timestamps
        from datetime import datetime, timezone, timedelta
        bkk_tz = timezone(timedelta(hours=7))
        entry_time = datetime.fromtimestamp(t["fill_time_ts"], tz=timezone.utc).astimezone(bkk_tz).strftime('%d-%m-%Y %H:%M:%S') if "fill_time_ts" in t else ""
        close_time = datetime.fromtimestamp(t["exit_time_ts"], tz=timezone.utc).astimezone(bkk_tz).strftime('%d-%m-%Y %H:%M:%S') if "exit_time_ts" in t else ""
        
        row = {
            "Time (BKK)": entry_time,
            "Close Time": close_time,
            "lts_leg": t["lts_leg"],
            "TF": t["tf"],
            "Type": t.get("signal", ""),
            "Entry": t.get("entry", 0.0),
            "SL": t.get("sl", 0.0),
            "TP": t.get("tp", 0.0),
            "Lot": round(t["lot_scaled"], 2),
            "P&L": round(t["pnl_usd_scaled"], 2),
            "Balance": round(running_balance, 2),
            "Reason": t.get("outcome", "")
        }
        csv_rows.append(row)
        
    if csv_rows:
        out_csv = os.path.join(os.path.dirname(__file__), '..', 'excel', 'lts_sim_trades.csv')
        with open(out_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=csv_rows[0].keys())
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"Exported {out_csv} successfully.")
    
    # Verify reconstruction
    final_pnl = P_matrix @ W_orig
    print(f"Reconstructed Avg $/day: {final_pnl.mean():.2f}")
    print(f"Reconstructed Worst day: {final_pnl.min():.2f}")
    
    # Export Daily Summary CSV
    daily_csv_rows = []
    daily_balance = START_BALANCE
    for d, pnl in zip(dates, final_pnl):
        if pnl != 0.0 or True: # Keep all dates or filter? Keep all to see timeline
            daily_balance += float(pnl)
            daily_csv_rows.append({
                "Date": d,
                "Daily P&L": round(float(pnl), 2),
                "Balance": round(daily_balance, 2)
            })
            
    if daily_csv_rows:
        out_daily_csv = os.path.join(os.path.dirname(__file__), '..', 'excel', 'lts_sim_daily.csv')
        with open(out_daily_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["Date", "Daily P&L", "Balance"])
            writer.writeheader()
            writer.writerows(daily_csv_rows)
        print(f"Exported {out_daily_csv} successfully.")

if __name__ == "__main__":
    main()
