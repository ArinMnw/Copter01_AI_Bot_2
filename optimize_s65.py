"""
optimize_s65.py - grid search for S65 All-in-4S Fake Reversal Trap.
"""

import argparse
import csv
import itertools
import os
from datetime import datetime

import MetaTrader5 as mt5

import config
from strategy65 import S65_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s65_backtest as s65sim
from sim_s62_backtest import _atr_series


def _fetch_by_tf(tfs, days):
    out = {}
    if not config.mt5_initialize(mt5):
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return out
    for tf in tfs:
        out[tf] = s30sim.fetch_bars(config.SYMBOL, tf, days, extra_bars=620)
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
        lookbacks = [54, 72]
        impulses = [2.5, 3.0]
        cmins = [0.20, 0.30]
        cmaxes = [0.75, 0.90]
        windows = [6, 10]
        minbodies = [0.12, 0.20]
        wicks = [0.05, 0.12]
        sls = [0.25, 0.45]
        tp_modes = ["rr"]
        rrs = [0.9, 1.15]
    else:
        tfs = ["M1", "M5", "M15", "M30"]
        lookbacks = [42, 54, 72, 96]
        impulses = [2.0, 2.5, 3.0, 3.8]
        cmins = [0.15, 0.25, 0.35]
        cmaxes = [0.70, 0.85, 1.00]
        windows = [5, 8, 12]
        minbodies = [0.08, 0.15, 0.25]
        wicks = [0.00, 0.08, 0.15]
        sls = [0.15, 0.30, 0.50]
        tp_modes = ["rr", "origin"]
        rrs = [0.75, 1.0, 1.25, 1.6]

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
    for tf, lb, imp, cmn, cmx, win, mb, wick, sl, tpm, rr in itertools.product(
        tfs, lookbacks, impulses, cmins, cmaxes, windows, minbodies, wicks, sls, tp_modes, rrs
    ):
        if cmn >= cmx:
            continue
        bars = bars_by_tf.get(tf)
        if bars is None:
            continue
        total += 1
        cfg = dict(S65_DEFAULTS)
        cfg.update(ENTRY_TF=tf, LOOKBACK=lb, IMPULSE_MIN_ATR=imp,
                   COUNTER_MIN_RETRACE=cmn, COUNTER_MAX_RETRACE=cmx,
                   FAKE_WINDOW=win, MIN_REV_BODY_ATR=mb, WICK_ATR=wick,
                   SL_ATR_MULT=sl, TP_MODE=tpm, TP_RR=rr)
        cfg.update(cache_by_tf.get(tf, {}))
        raw = s65sim.run_single(bars, cfg, args.days, spread)
        fs = s65sim._fixed_lot_stats(raw, args.days, spread)
        label = f"{tf}_lb{lb}_imp{imp}_c{cmn}-{cmx}_w{win}_mb{mb}_wk{wick}_sl{sl}_{tpm}_rr{rr}"
        rows.append({"label": label, "entry_tf": tf, "lookback": lb, "impulse": imp,
                     "counter_min": cmn, "counter_max": cmx, "window": win,
                     "min_body": mb, "wick": wick, "sl": sl, "tp_mode": tpm,
                     "rr": rr, **fs})
        if total % 50 == 0:
            best = max(rows, key=lambda r: (r["fixed_pf"], r["sharpe_like"], r["fixed_per_day"]))
            print(f"{total} combos | best PF={best['fixed_pf']:.2f} $/d={best['fixed_per_day']:.2f} "
                  f"sharpe={best['sharpe_like']:.3f} n={best['trades']} {best['label']}")

    rows.sort(key=lambda r: (r["fixed_pf"], r["sharpe_like"], r["fixed_per_day"]), reverse=True)
    out = "s65_optimize_summary.csv"
    fields = ["timestamp", "label", "entry_tf", "lookback", "impulse", "counter_min",
              "counter_max", "window", "min_body", "wick", "sl", "tp_mode", "rr",
              "trades", "wr", "fixed_pnl", "fixed_per_day", "fixed_per_month",
              "fixed_pf", "fixed_avg", "pct_pos_days", "max_losing_day_streak",
              "sharpe_like"]
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
