"""
optimize_s63.py - grid search for S63 All-in-4S DMxSP/FVG Reclaim.
"""

import argparse
import csv
import itertools
import os
from datetime import datetime

import MetaTrader5 as mt5

import config
from strategy63 import S63_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s63_backtest as s63sim
from sim_s62_backtest import _atr_series


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
        "_ATR14": _atr_series(bars, 14),
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
        modes = ["breakout", "either"]
        sp_lbs = [8, 12]
        sp_maxes = [1.4]
        fvg_required = [True, False]
        fvg_mins = [0.0]
        min_bodies = [0.20, 0.35]
        body_ratios = [0.40]
        sls = [0.35, 0.60]
        rrs = [0.9, 1.2]
    else:
        tfs = ["M5", "M15", "M30"]
        modes = ["sweep_reclaim", "breakout", "either"]
        sp_lbs = [8, 12, 18]
        sp_maxes = [0.8, 1.2, 1.8]
        fvg_required = [True, False]
        fvg_mins = [0.0, 0.03, 0.08]
        min_bodies = [0.18, 0.30, 0.45]
        body_ratios = [0.35, 0.50, 0.65]
        sls = [0.35, 0.60, 0.90]
        rrs = [0.8, 1.1, 1.5]

    bars_by_tf = _fetch_by_tf(tfs, args.days)
    cache_by_tf = {tf: _cache_for_bars(bars) for tf, bars in bars_by_tf.items() if bars is not None}
    rows = []
    total = 0
    for tf, mode, lb, spm, fvg, fmin, mb, br, sl, rr in itertools.product(
        tfs, modes, sp_lbs, sp_maxes, fvg_required, fvg_mins, min_bodies, body_ratios, sls, rrs
    ):
        bars = bars_by_tf.get(tf)
        if bars is None:
            continue
        total += 1
        cfg = dict(S63_DEFAULTS)
        cfg.update(
            ENTRY_TF=tf,
            MODE=mode,
            SP_LOOKBACK=lb,
            SP_MAX_ATR=spm,
            FVG_REQUIRED=fvg,
            FVG_MIN_ATR=fmin,
            MIN_BODY_ATR=mb,
            MIN_BODY_RATIO=br,
            SL_ATR_MULT=sl,
            TP_RR=rr,
        )
        cfg.update(cache_by_tf.get(tf, {}))
        raw = s63sim.run_single(bars, cfg, args.days, spread)
        fs = s63sim._fixed_lot_stats(raw, args.days, spread)
        label = f"{tf}_{mode}_lb{lb}_sp{spm}_fvg{int(fvg)}_fm{fmin}_mb{mb}_br{br}_sl{sl}_rr{rr}"
        rows.append({
            "label": label, "entry_tf": tf, "mode": mode, "sp_lookback": lb,
            "sp_max_atr": spm, "fvg_required": fvg, "fvg_min_atr": fmin,
            "min_body_atr": mb, "body_ratio": br, "sl": sl, "rr": rr, **fs,
        })
        if total % 20 == 0:
            best = max(rows, key=lambda r: (r["fixed_pf"], r["sharpe_like"], r["fixed_per_day"]))
            print(
                f"{total} combos | best PF={best['fixed_pf']:.2f} $/d={best['fixed_per_day']:.2f} "
                f"sharpe={best['sharpe_like']:.3f} n={best['trades']} {best['label']}"
            )

    rows.sort(key=lambda r: (r["fixed_pf"], r["sharpe_like"], r["fixed_per_day"]), reverse=True)
    out = "s63_optimize_summary.csv"
    fields = [
        "timestamp", "label", "entry_tf", "mode", "sp_lookback", "sp_max_atr",
        "fvg_required", "fvg_min_atr", "min_body_atr", "body_ratio", "sl", "rr",
        "trades", "wr", "fixed_pnl", "fixed_per_day", "fixed_per_month",
        "fixed_pf", "fixed_avg", "pct_pos_days", "max_losing_day_streak", "sharpe_like",
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
