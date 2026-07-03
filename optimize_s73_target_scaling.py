"""
optimize_s73_target_scaling.py - Scaling audit for S72 vs the $1000/day target.

RESEARCH/BACKTEST-ONLY. No live bot wiring.

This script uses cached raw trades from optimize_s72_vs_demo_portfolio.py and
answers a narrower question:
- If S72 beats P13/P16 at fixed-lot size, what scale is required to reach
  $1000/day?
- What happens to the worst daily loss at that scale?
"""

import argparse
import csv
import os
from datetime import datetime

import config
import sim_s31_backtest as s31sim

from optimize_s72_vs_demo_portfolio import (
    DEFAULT_SPREAD,
    ROOT_DIR,
    _aggregate_raw,
    _load_cache,
    _weighted_stats_from_agg,
)


TARGET_WEIGHTS = {
    "P13_BASE": 1.0,
    "S63": 8.0,
    "S69": 24.0,
    "S64": 4.0,
}


def _base_weights(raw_payload, base):
    agg = _aggregate_raw(raw_payload[base], DEFAULT_SPREAD)
    return {leg: 1.0 for leg in agg}


def _combined_agg(raw_payload, base):
    return _aggregate_raw(raw_payload[base] + raw_payload["ALLIN"], DEFAULT_SPREAD)


def _daily_series_from_agg(agg, weights):
    by_day = {}
    by_leg = {}
    for leg, row in agg.items():
        w = float(weights.get(leg, 0.0))
        if w <= 0:
            continue
        by_leg[leg] = float(row["total"]) * w
        for d, pnl in row["by_day"].items():
            by_day[d] = by_day.get(d, 0.0) + float(pnl) * w
    return by_day, by_leg


def _stats_with_scale(agg, days, weights, scale):
    scaled_weights = {k: v * scale for k, v in weights.items()}
    stats = _weighted_stats_from_agg(agg, days, scaled_weights)
    by_day, by_leg = _daily_series_from_agg(agg, scaled_weights)
    vals = list(by_day.values())
    stats["worst_day"] = round(min(vals), 2) if vals else 0.0
    stats["best_day"] = round(max(vals), 2) if vals else 0.0
    stats["by_leg"] = by_leg
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="90,120,150,180")
    ap.add_argument("--target-day", type=float, default=1000.0)
    ap.add_argument("--cache-dir", default=os.path.join(ROOT_DIR, "tmp", "s72_cache"))
    ap.add_argument("--out", default="s73_target_scaling_audit.csv")
    args = ap.parse_args()
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]

    base_rows = []
    for days in windows:
        payload = _load_cache(args.cache_dir, days, DEFAULT_SPREAD)
        if payload is None:
            raise SystemExit(f"missing cache for {days}d; run optimize_s72_vs_demo_portfolio.py first")
        agg = _combined_agg(payload, "P13")
        weights = _base_weights(payload, "P13")
        weights.update({"S63": TARGET_WEIGHTS["S63"], "S69": TARGET_WEIGHTS["S69"], "S64": TARGET_WEIGHTS["S64"]})
        stats = _stats_with_scale(agg, days, weights, 1.0)
        base_rows.append({"days": days, "agg": agg, "weights": weights, **stats})

    min_day = min(r["fixed_per_day"] for r in base_rows)
    avg_day = sum(r["fixed_per_day"] for r in base_rows) / len(base_rows)
    scale_for_all_windows = args.target_day / min_day if min_day > 0 else 0.0
    scale_for_avg = args.target_day / avg_day if avg_day > 0 else 0.0

    rows = []
    for label, scale in (
        ("S72_FIXED", 1.0),
        ("S73_AVG_1000", scale_for_avg),
        ("S73_ALL_WINDOWS_1000", scale_for_all_windows),
    ):
        for r in base_rows:
            stats = _stats_with_scale(r["agg"], r["days"], r["weights"], scale)
            rows.append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "label": label,
                "scale": round(scale, 3),
                "days": r["days"],
                "fixed_per_day": stats["fixed_per_day"],
                "fixed_per_month": stats["fixed_per_month"],
                "fixed_pf": stats["fixed_pf"],
                "sharpe_like": stats["sharpe_like"],
                "max_losing_day_streak": stats["max_losing_day_streak"],
                "worst_day": stats["worst_day"],
                "best_day": stats["best_day"],
                "trade_units": stats["trade_units"],
            })

    fields = [
        "timestamp", "label", "scale", "days", "fixed_per_day", "fixed_per_month",
        "fixed_pf", "sharpe_like", "max_losing_day_streak", "worst_day",
        "best_day", "trade_units",
    ]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print(f"S72 fixed avg$/d={avg_day:.2f}, minWindow$/d={min_day:.2f}")
    print(f"scale for avg $1000/day: {scale_for_avg:.2f}x")
    print(f"scale for every window >= $1000/day: {scale_for_all_windows:.2f}x")
    print("\nRows:")
    for row in rows:
        print(
            f"{row['label']} {row['days']}d scale={row['scale']} "
            f"$/d={row['fixed_per_day']:.2f} PF={row['fixed_pf']:.2f} "
            f"st={row['max_losing_day_streak']} worstDay={row['worst_day']:.2f}"
        )
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
