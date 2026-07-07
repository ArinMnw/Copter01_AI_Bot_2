import csv
import itertools
import argparse
from datetime import datetime
import MetaTrader5 as mt5

import config
import sim_s30_backtest as s30sim
from sim_s62_backtest import _atr_series
from sim_s86_backtest import run_single as run_s86
from optimize_s72_vs_demo_portfolio import DEFAULT_SPREAD
from optimize_s87_siglevel_fast import _invert_raw
from optimize_s88_allin4s_fast import _grid_s86, _make_s86, TF_EXTRA_BARS, OVERLAY_CFG
from optimize_s75_champion_formula import _simulate_leg

def _calc_pf(trades):
    profit = sum(t.get("pnl", 0) for t in trades if t.get("pnl", 0) > 0)
    loss = sum(abs(t.get("pnl", 0)) for t in trades if t.get("pnl", 0) < 0)
    return profit / loss if loss > 0 else (99.0 if profit > 0 else 0.0)

def _calc_sum(trades):
    return sum(t.get("pnl", 0) for t in trades)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="s86_screen_results.csv")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=8192)
    args = ap.parse_args()

    grid = _grid_s86("micro")
    all_vals = list(itertools.product(*grid))
    
    if not config.mt5_initialize(mt5):
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
        
    try:
        bars_cache = {}
        for tf in ["M15", "M30"]:
            bars = s30sim.fetch_bars(config.SYMBOL, tf, 180, extra_bars=TF_EXTRA_BARS.get(tf, 700))
            bars_cache[tf] = bars
            
        with open(args.out, "a" if args.start > 0 else "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=[
                "idx", "tf", "n_dir", "dir_sum", "dir_pf", "n_inv", "inv_sum", "inv_pf", "cfg_str"
            ])
            if args.start == 0:
                w.writeheader()
                
            count = 0
            for idx in range(args.start, min(args.end, len(all_vals))):
                vals = all_vals[idx]
                cfg = _make_s86(vals)
                tf = cfg["ENTRY_TF"]
                bars = bars_cache[tf]
                
                run_cfg = dict(cfg)
                run_cfg["_ATR14"] = _atr_series(bars, 14)
                run_cfg["_DT_BKK"] = [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]
                
                # Direct
                raw_dir = run_s86(bars, run_cfg, 180, DEFAULT_SPREAD)
                _twp_dir, eq_dir, by_day_dir = _simulate_leg(raw_dir, OVERLAY_CFG)
                dir_sum = sum(by_day_dir.values())
                dir_pf = _calc_pf(raw_dir) # wait, _simulate_leg modifies raw?
                
                # Inverse
                raw_inv = _invert_raw(raw_dir)
                _twp_inv, eq_inv, by_day_inv = _simulate_leg(raw_inv, OVERLAY_CFG)
                inv_sum = sum(by_day_inv.values())
                inv_pf = _calc_pf(raw_inv)
                
                cfg_str = (
                    f"S86RUN_{tf}_lb{cfg['LOOKBACK']}_imp{cfg['IMPULSE_MIN_ATR']:g}"
                    f"_zt{cfg['ZONE_TOL_ATR']:g}_body{cfg['CONFIRM_BODY_ATR']:g}"
                    f"_ratio{cfg['CONFIRM_BODY_RATIO']:g}_tr{int(cfg['REQUIRE_TREND'])}"
                    f"_tl{cfg['TREND_LOOKBACK']}_tm{cfg['TREND_MIN_ATR']:g}"
                    f"_{cfg['SL_MODE']}_{cfg['TP_MODE']}_sl{cfg['SL_ATR_MULT']:g}_rr{cfg['TP_RR']:g}"
                )
                
                w.writerow({
                    "idx": idx,
                    "tf": tf,
                    "n_dir": len(raw_dir),
                    "dir_sum": round(dir_sum, 2),
                    "dir_pf": round(dir_pf, 3),
                    "n_inv": len(raw_inv),
                    "inv_sum": round(inv_sum, 2),
                    "inv_pf": round(inv_pf, 3),
                    "cfg_str": cfg_str
                })
                f.flush()
                
                count += 1
                if count % 100 == 0:
                    print(f"Processed {idx + 1} / 8192 configs...")
                    
        print(f"Done! Evaluated {count} configs. Results in {args.out}")
                
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    main()
