import argparse
import csv
import itertools
from datetime import datetime
import MetaTrader5 as mt5
import numpy as np

import config
import sim_s30_backtest as s30sim
from optimize_s87_siglevel_fast import _invert_raw, _load_base_daily, _max_losing_streak, _pf
from optimize_s88_allin4s_fast import _make_s84, _make_s86, _grid_s84, _grid_s86, TF_EXTRA_BARS, OVERLAY_CFG, _cfg_label, _daily_rows, _summ, _floor_flags
from optimize_s75_champion_formula import _simulate_leg
from sim_s84_backtest import run_single as run_s84
from sim_s86_backtest import run_single as run_s86
from sim_s62_backtest import _atr_series
from optimize_s72_vs_demo_portfolio import DEFAULT_SPREAD

def _risk_atr(trade):
    import re
    match = re.search(r"riskATR=([0-9.]+)", str(trade.get("reason", "")))
    return float(match.group(1)) if match else 0.0

def _post_filter_raw(raw, rd_band, fill_hour):
    out = []
    rd_min, rd_max = 0.0, 0.0
    if rd_band != "all":
        parts = rd_band.split("-")
        rd_min, rd_max = float(parts[0]), float(parts[1])
        
    for trade in raw:
        # RD Filter
        if rd_band != "all":
            rd = float(trade.get("risk_distance", 0.0))
            if rd < rd_min or rd > rd_max:
                continue
                
        # Hour Filter
        if fill_hour >= 0:
            hour = config.mt5_ts_to_bkk(int(trade["fill_time_ts"])).hour
            if hour != fill_hour:
                continue
                
        out.append(trade)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--w-max", type=float, default=600)
    ap.add_argument("--w-step", type=float, default=1.0)
    ap.add_argument("--family", choices=["s84", "s86"], default="s86")
    ap.add_argument("--cfg-idx", type=int, required=True)
    ap.add_argument("--out", default="ambfix_sweep_results.csv")
    ap.add_argument("--floor", type=float, default=-1000.0)
    args = ap.parse_args()

    windows = [90, 120, 150, 180]
    floors = [-700, -900, -973.16, -999.91, -1000]
    
    grid = _grid_s84("micro") if args.family == "s84" else _grid_s86("micro")
    all_vals = list(itertools.product(*grid))
    cfg_vals = all_vals[args.cfg_idx]
    
    maker = _make_s84 if args.family == "s84" else _make_s86
    runner = run_s84 if args.family == "s84" else run_s86
    cfg = maker(cfg_vals)
    tf = cfg["ENTRY_TF"]

    if not config.mt5_initialize(mt5):
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
        
    try:
        bars_by_days = {days: s30sim.fetch_bars(config.SYMBOL, tf, days, extra_bars=TF_EXTRA_BARS.get(tf, 700)) for days in windows}
    finally:
        mt5.shutdown()

    base_daily = _load_base_daily(args.base, windows)
    base_rows = _daily_rows(base_daily, windows)
    for r in base_rows: r["skipped"] = 0
    base_summary = _summ(base_rows)

    print(f"Base avg: {base_summary['avg_day']:.2f}, min: {base_summary['min_day']:.2f}")

    bands = ["all", "0.8-1.3", "1.3-2.0", "2.0-2.7", "2.7-3.4", "3.4-4.0", "4.0-5.0", "5.0-7.0"]
    hours = list(range(24))
    modes = ["direct", "inverse"]
    
    raw_dir_by_days = {}
    for days in windows:
        bars = bars_by_days[days]
        run_cfg = dict(cfg)
        run_cfg["_ATR14"] = _atr_series(bars, 14)
        run_cfg["_DT_BKK"] = [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]
        raw_dir_by_days[days] = runner(bars, run_cfg, days, DEFAULT_SPREAD)
        
    candidates = []
    
    for mode in modes:
        for band in bands:
            for hour in hours:
                # Get raw trades filtered
                raw_counts = {}
                leg_arrays = {}
                for days in windows:
                    raw = _post_filter_raw(raw_dir_by_days[days], band, hour)
                    if mode == "inverse":
                        raw = _invert_raw(raw)
                    _twp, eq, by_day = _simulate_leg(raw, OVERLAY_CFG)
                    dates = [d for d, _v in base_daily[days]]
                    leg_arrays[days] = np.array([float(by_day.get(d, 0.0)) for d in dates], dtype=float)
                    raw_counts[days] = len(raw)
                    
                if raw_counts[180] == 0:
                    continue
                    
                # Binary search for best weight roughly, or just step through
                best_summary = None
                best_weight = 0
                best_rows = None
                for w in np.arange(args.w_step, args.w_max + args.w_step, args.w_step):
                    rows = []
                    valid = True
                    for days in windows:
                        base_vals = np.array([v for _d, v in base_daily[days]], dtype=float)
                        vals = base_vals + leg_arrays[days] * w
                        streak = _max_losing_streak(vals)
                        worst_day = float(vals.min())
                        if streak > 3 or worst_day < args.floor:
                            valid = False
                            break
                        rows.append({
                            "days": days,
                            "day": float(vals.sum()) / days,
                            "pf": _pf(vals),
                            "streak": streak,
                            "worst_day": worst_day,
                            "best_day": float(vals.max()),
                            "max_lot": 0, "max_dd": 0, "skipped": 0
                        })
                        
                    if not valid:
                        break # hit cap
                        
                    summary = _summ(rows)
                    if summary["avg_day"] > base_summary["avg_day"] and summary["min_day"] > base_summary["min_day"]:
                        best_summary = summary
                        best_weight = w
                        best_rows = rows
                
                if best_summary:
                    label = f"{mode.upper()}_S{args.family[1:]}c{args.cfg_idx}_RD{band}_H{hour}"
                    candidates.append((best_summary["avg_day"], best_summary["min_day"], label, best_weight, best_summary, best_rows, raw_counts))
                    
    candidates.sort(key=lambda x: (x[1], x[0]), reverse=True)
    
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["label", "weight", "avg", "min", "worst", "raw_counts"])
        for _, _, label, weight, summary, _rows, raw_counts in candidates[:100]:
            rc = ";".join(f"{k}d:{v}" for k, v in sorted(raw_counts.items()))
            w.writerow([label, round(weight, 3), round(summary["avg_day"], 2), round(summary["min_day"], 2), round(summary["worst_day"], 2), rc])
            
    print(f"Top 5 candidates:")
    for _, _, label, weight, summary, _rows, raw_counts in candidates[:5]:
        print(f"{label} w={weight:.3f} avg={summary['avg_day']:.2f} min={summary['min_day']:.2f}")
    print(f"Results written to {args.out}")

if __name__ == "__main__":
    main()
