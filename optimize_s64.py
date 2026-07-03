"""
optimize_s64.py - grid search for S64 All-in-4S KRH Fibo Expansion Hold.
"""

import argparse
import csv
import itertools
import os
from datetime import datetime

import MetaTrader5 as mt5

import config
from strategy64 import S64_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s64_backtest as s64sim
from sim_s62_backtest import _atr_series


def _fetch_by_tf(tfs, days):
    out = {}
    if not config.mt5_initialize(mt5):
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return out
    for tf in tfs:
        out[tf] = s30sim.fetch_bars(config.SYMBOL, tf, days, extra_bars=560)
    mt5.shutdown()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    spread = 0.20
    if args.quick:
        tfs = ["M5", "M15"]
        seed_lbs = [36]
        levels = [1.617, 3.097]
        targets = [3.097, 5.165]
        modes = ["hold", "break"]
        seed_mins = [0.25]
        seed_maxes = [1.8]
        min_bodies = [0.12, 0.25]
        sl_levels = [0.0, 1.617]
        sls = [0.25]
        tp_modes = ["krh", "rr"]
        rrs = [1.2]
    else:
        tfs = ["M5", "M15", "M30"]
        seed_lbs = [24, 36, 60]
        levels = [1.617, 3.097, 5.165]
        targets = [3.097, 5.165, 7.044]
        modes = ["hold", "break"]
        seed_mins = [0.15, 0.25, 0.40]
        seed_maxes = [1.4, 2.0]
        min_bodies = [0.10, 0.20, 0.35]
        sl_levels = [0.0, 1.617, 3.097]
        sls = [0.10, 0.30, 0.50]
        tp_modes = ["krh", "rr"]
        rrs = [0.8, 1.1, 1.5]

    bars_by_tf = _fetch_by_tf(tfs, args.days)
    cache_by_tf = {
        tf: {
            "_ATR14": _atr_series(bars, 14),
            "_DT_BKK": [config.mt5_ts_to_bkk(int(b["time"])) for b in bars],
        }
        for tf, bars in bars_by_tf.items() if bars is not None
    }
    rows = []
    total = 0
    for tf, slb, lvl, tgt, mode, smn, smx, mb, sll, slm, tpm, rr in itertools.product(
        tfs, seed_lbs, levels, targets, modes, seed_mins, seed_maxes, min_bodies,
        sl_levels, sls, tp_modes, rrs
    ):
        if tgt <= lvl:
            continue
        bars = bars_by_tf.get(tf)
        if bars is None:
            continue
        total += 1
        cfg = dict(S64_DEFAULTS)
        cfg.update(ENTRY_TF=tf, SEED_LOOKBACK=slb, LEVEL=lvl, TARGET_LEVEL=tgt, MODE=mode,
                   SEED_MIN_BODY_ATR=smn, SEED_MAX_BODY_ATR=smx, MIN_BODY_ATR=mb,
                   SL_LEVEL=sll, SL_ATR_MULT=slm, TP_MODE=tpm, TP_RR=rr)
        cfg.update(cache_by_tf.get(tf, {}))
        raw = s64sim.run_single(bars, cfg, args.days, spread)
        fs = s64sim._fixed_lot_stats(raw, args.days, spread)
        label = f"{tf}_{mode}_slb{slb}_lv{lvl}_tg{tgt}_smn{smn}_mb{mb}_sll{sll}_sl{slm}_{tpm}_rr{rr}"
        rows.append({"label": label, "entry_tf": tf, "seed_lookback": slb, "level": lvl,
                     "target": tgt, "mode": mode, "seed_min": smn, "min_body": mb,
                     "sl_level": sll, "sl": slm, "tp_mode": tpm, "rr": rr, **fs})
        if total % 20 == 0:
            best = max(rows, key=lambda r: (r["fixed_pf"], r["sharpe_like"], r["fixed_per_day"]))
            print(f"{total} combos | best PF={best['fixed_pf']:.2f} $/d={best['fixed_per_day']:.2f} "
                  f"sharpe={best['sharpe_like']:.3f} n={best['trades']} {best['label']}")

    rows.sort(key=lambda r: (r["fixed_pf"], r["sharpe_like"], r["fixed_per_day"]), reverse=True)
    out = "s64_optimize_summary.csv"
    fields = ["timestamp", "label", "entry_tf", "seed_lookback", "level", "target", "mode",
              "seed_min", "min_body", "sl_level", "sl", "tp_mode", "rr", "trades", "wr",
              "fixed_pnl", "fixed_per_day", "fixed_per_month", "fixed_pf", "fixed_avg",
              "pct_pos_days", "max_losing_day_streak", "sharpe_like"]
    is_new = not os.path.exists(out)
    with open(out, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if is_new:
            w.writeheader()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for r in rows:
            w.writerow({"timestamp": ts, **{k: r.get(k) for k in fields if k != "timestamp"}})

    print("\nTop 20 fixed-lot candidates:")
    for i, r in enumerate(rows[:20], 1):
        print(f"{i:>2}. PF={r['fixed_pf']:.3f} $/d={r['fixed_per_day']:>7.2f} "
              f"sharpe={r['sharpe_like']:.3f} n={r['trades']:>4} "
              f"streak={r['max_losing_day_streak']} {r['label']}")
    print(f"\n-> {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
