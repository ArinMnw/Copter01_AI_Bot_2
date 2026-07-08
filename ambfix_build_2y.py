import argparse
import csv
import itertools
from datetime import datetime
import MetaTrader5 as mt5
import numpy as np

import config
import sim_s30_backtest as s30sim
from optimize_s87_siglevel_fast import _invert_raw, _load_base_daily, _max_losing_streak, _pf
from optimize_s88_allin4s_fast import _make_s84, _make_s86, _grid_s84, _grid_s86, TF_EXTRA_BARS, OVERLAY_CFG, _cfg_label, _daily_rows, _summ
from optimize_s75_champion_formula import _simulate_leg
from sim_s84_backtest import run_single as run_s84
from sim_s86_backtest import run_single as run_s86
from sim_s62_backtest import _atr_series
from optimize_s72_vs_demo_portfolio import DEFAULT_SPREAD

def _post_filter_raw(raw, rd_band, fill_hour):
    out = []
    rd_min, rd_max = 0.0, 0.0
    if rd_band != "all":
        parts = rd_band.split("-")
        rd_min, rd_max = float(parts[0]), float(parts[1])
        
    for trade in raw:
        if rd_band != "all":
            rd = float(trade.get("risk_distance", 0.0))
            if rd < rd_min or rd > rd_max:
                continue
        if fill_hour >= 0:
            hour = config.mt5_ts_to_bkk(int(trade["fill_time_ts"])).hour
            if hour != fill_hour:
                continue
        out.append(trade)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--family", choices=["s84", "s86"], default="s86")
    ap.add_argument("--cfg-idx", type=int, required=True)
    ap.add_argument("--mode", choices=["direct", "inverse"], required=True)
    ap.add_argument("--rd-band", default="all")
    ap.add_argument("--h", type=int, default=-1)
    ap.add_argument("--w-lo", type=float, required=True)
    ap.add_argument("--w-hi", type=float, required=True)
    ap.add_argument("--out-prefix", required=True)
    ap.add_argument("--floor", type=float, default=-1000.0)
    args = ap.parse_args()

    windows = [550]
    
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

    raw_dir_by_days = {}
    for days in windows:
        bars = bars_by_days[days]
        run_cfg = dict(cfg)
        run_cfg["_ATR14"] = _atr_series(bars, 14)
        run_cfg["_DT_BKK"] = [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]
        raw_dir_by_days[days] = runner(bars, run_cfg, days, DEFAULT_SPREAD)
        
    leg_arrays = {}
    for days in windows:
        raw = _post_filter_raw(raw_dir_by_days[days], args.rd_band, args.h)
        if args.mode == "inverse":
            raw = _invert_raw(raw)
        _twp, eq, by_day = _simulate_leg(raw, OVERLAY_CFG)
        dates = [d for d, _v in base_daily[days]]
        leg_arrays[days] = np.array([float(by_day.get(d, 0.0)) for d in dates], dtype=float)

    # Sweep weights precisely
    w_grid = np.arange(args.w_lo, args.w_hi + 0.001, 0.001)
    
    probe_rows = []
    best_summary = None
    best_weight = 0
    best_vals = None
    
    for w in w_grid:
        valid = True
        rows = []
        for days in windows:
            base_vals = np.array([v for _d, v in base_daily[days]], dtype=float)
            vals = base_vals + leg_arrays[days] * w
            streak = _max_losing_streak(vals)
            worst_day = float(vals.min())
            
            rows.append({
                "days": days,
                "day": float(vals.sum()) / days,
                "worst_day": worst_day,
                "streak": streak,
                "pf": _pf(vals),
                "best_day": float(vals.max()),
                "max_lot": 0.0,
                "max_dd": 0.0,
                "skipped": 0
            })
            
            if streak > 3 or worst_day < args.floor:
                valid = False
                break
                
        if not valid:
            continue
            
        summary = _summ(rows)
        probe_rows.append({
            "weight": round(w, 3),
            "valid": valid,
            "avg_day": round(summary["avg_day"], 4),
            "min_day": round(summary["min_day"], 4),
            "worst_day": round(summary["worst_day"], 4),
            "streak": summary["max_streak"]
        })
        
        if not best_summary or summary["min_day"] > best_summary["min_day"]:
            best_summary = summary
            best_weight = w
            best_vals = {}
            for days in windows:
                base_v = np.array([v for _d, v in base_daily[days]], dtype=float)
                best_vals[days] = base_v + leg_arrays[days] * w

    if not best_summary:
        print("No valid weight found!")
        return
        
    print(f"Best weight: {best_weight:.3f} | avg: {best_summary['avg_day']:.2f} | min: {best_summary['min_day']:.2f} | worst: {best_summary['worst_day']:.2f}")
    
    # Save Daily
    daily_file = f"{args.out_prefix}_daily.csv"
    with open(daily_file, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["days", "date", "total"])
        w.writeheader()
        for days in windows:
            dates = [d for d, _v in base_daily[days]]
            vals = best_vals[days]
            for date, val in zip(dates, vals):
                w.writerow({"days": days, "date": date, "total": round(val, 6)})
                
    # Save Probe
    probe_file = f"{args.out_prefix}_probe.csv"
    with open(probe_file, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["weight", "valid", "avg_day", "min_day", "worst_day", "streak"])
        w.writeheader()
        w.writerows(probe_rows)
        
    print(f"Saved {daily_file} and {probe_file}")

if __name__ == "__main__":
    main()
