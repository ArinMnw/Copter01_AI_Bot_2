"""
optimize_s62.py - grid search for S62 All-in-4S Close-Cover Reversal.
"""

import argparse
import csv
import itertools
import os
from datetime import datetime

import MetaTrader5 as mt5

import config
from strategy62 import S62_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s62_backtest as s62sim


def _fetch_by_tf(tfs, days):
    out = {}
    if not config.mt5_initialize(mt5):
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return out
    for tf in tfs:
        out[tf] = s30sim.fetch_bars(config.SYMBOL, tf, days, extra_bars=480)
    mt5.shutdown()
    return out


def _cache_for_bars(bars):
    return {
        "_CLOSES": [float(b["close"]) for b in bars],
        "_ATR14": s62sim._atr_series(bars, 14),
        "_DT_BKK": [config.mt5_ts_to_bkk(int(b["time"])) for b in bars],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    spread = 0.20

    if args.quick:
        tfs = ["M5", "M15"]
        level_modes = ["sweep", "sweep_or_round", "near"]
        cover_modes = ["body", "wick"]
        trend_lbs = [8, 12]
        pivot_lbs = [8]
        level_lbs = [60]
        min_bodies = [0.10, 0.18]
        max_bodies = [1.8]
        body_ratios = [0.30, 0.45]
        first_waves = [12]
        sls = [0.35, 0.60]
        rrs = [0.9, 1.2]
    else:
        tfs = ["M5", "M15", "M30"]
        level_modes = ["sweep", "near", "round", "sweep_or_round"]
        cover_modes = ["body", "wick"]
        trend_lbs = [6, 10, 14]
        pivot_lbs = [5, 8, 12]
        level_lbs = [36, 60, 96]
        min_bodies = [0.08, 0.15, 0.25]
        max_bodies = [1.2, 1.8, 2.4]
        body_ratios = [0.30, 0.40, 0.55]
        first_waves = [8, 14, 22]
        sls = [0.30, 0.50, 0.80]
        rrs = [0.8, 1.1, 1.5]

    bars_by_tf = _fetch_by_tf(tfs, args.days)
    cache_by_tf = {tf: _cache_for_bars(bars) for tf, bars in bars_by_tf.items() if bars is not None}
    rows = []
    total = 0
    for tf, lm, cm, tl, pl, ll, mb, xb, br, fw, sl, rr in itertools.product(
        tfs, level_modes, cover_modes, trend_lbs, pivot_lbs, level_lbs,
        min_bodies, max_bodies, body_ratios, first_waves, sls, rrs
    ):
        bars = bars_by_tf.get(tf)
        if bars is None:
            continue
        total += 1
        cfg = dict(S62_DEFAULTS)
        cfg.update(
            ENTRY_TF=tf,
            LEVEL_MODE=lm,
            COVER_MODE=cm,
            TREND_LOOKBACK=tl,
            PIVOT_LOOKBACK=pl,
            LEVEL_LOOKBACK=ll,
            MIN_BODY_ATR=mb,
            MAX_BODY_ATR=xb,
            MIN_BODY_RATIO=br,
            FIRST_WAVE_BARS=fw,
            SL_ATR_MULT=sl,
            TP_RR=rr,
        )
        cfg.update(cache_by_tf.get(tf, {}))
        raw = s62sim.run_single(bars, cfg, args.days, spread)
        fs = s62sim._fixed_lot_stats(raw, args.days, spread)
        label = (
            f"{tf}_{lm}_{cm}_tr{tl}_pv{pl}_lv{ll}_mb{mb}_xb{xb}"
            f"_br{br}_fw{fw}_sl{sl}_rr{rr}"
        )
        rows.append({
            "label": label,
            "entry_tf": tf,
            "level_mode": lm,
            "cover_mode": cm,
            "trend": tl,
            "pivot": pl,
            "level_lookback": ll,
            "min_body": mb,
            "max_body": xb,
            "body_ratio": br,
            "first_wave": fw,
            "sl": sl,
            "rr": rr,
            **fs,
        })
        if total % 100 == 0:
            best = max(rows, key=lambda r: (r["fixed_pf"], r["sharpe_like"], r["fixed_per_day"]))
            print(
                f"{total} combos | best PF={best['fixed_pf']:.2f} "
                f"$/d={best['fixed_per_day']:.2f} sharpe={best['sharpe_like']:.3f} "
                f"n={best['trades']} {best['label']}"
            )

    rows.sort(key=lambda r: (r["fixed_pf"], r["sharpe_like"], r["fixed_per_day"]), reverse=True)
    out = "s62_optimize_summary.csv"
    fields = [
        "timestamp", "label", "entry_tf", "level_mode", "cover_mode", "trend",
        "pivot", "level_lookback", "min_body", "max_body", "body_ratio",
        "first_wave", "sl", "rr", "trades", "wr", "fixed_pnl",
        "fixed_per_day", "fixed_per_month", "fixed_pf", "fixed_avg",
        "pct_pos_days", "max_losing_day_streak", "sharpe_like",
    ]
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
        print(
            f"{i:>2}. PF={r['fixed_pf']:.3f} $/d={r['fixed_per_day']:>7.2f} "
            f"sharpe={r['sharpe_like']:.3f} n={r['trades']:>4} "
            f"streak={r['max_losing_day_streak']} {r['label']}"
        )
    print(f"\n-> {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
