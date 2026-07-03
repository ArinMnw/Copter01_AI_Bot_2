"""
optimize_s76_champion_search.py - Search for a portfolio that beats S75.

RESEARCH/BACKTEST-ONLY. No live bot wiring.

Uses the same sizing formula as P13/P16/S75:
    simulate_equity_substream(raw, cfg, START_EQUITY=1000)
per leg, then sum daily PnL across weighted legs.
"""

import argparse
import csv
import itertools
import os
from datetime import datetime

from optimize_s72_vs_demo_portfolio import DEFAULT_SPREAD, ROOT_DIR, _load_cache
from optimize_s75_champion_formula import (
    ALLIN_KEYS,
    DEMO_KEYS,
    P16_KEYS,
    _cfg_for_leg,
    _normalize_allin_raw,
    _normalize_demo_raw,
    _simulate_leg,
    _stats,
)


S75_WEIGHTS = {k: 1.0 for k in DEMO_KEYS + ALLIN_KEYS}
S75_WEIGHTS.update({"S63": 8.0, "S69": 24.0, "S64": 8.0})


def _summary(rows):
    return {
        "avg_day": sum(r["day"] for r in rows) / len(rows),
        "min_day": min(r["day"] for r in rows),
        "min_pf": min(r["daily_pf"] for r in rows),
        "max_streak": max(r["max_streak"] for r in rows),
        "worst_day": min(r["worst_day"] for r in rows),
        "max_lot": max(r["max_lot"] for r in rows),
        "max_leg_dd_pct": max(r["max_leg_dd_pct"] for r in rows),
        "skipped_by_cb": max(r["skipped_by_cb"] for r in rows),
    }


def _base_variants():
    variants = []
    full = {k: 1.0 for k in DEMO_KEYS + ALLIN_KEYS}
    for k in ALLIN_KEYS:
        full[k] = 0.0
    variants.append(("P16", full))

    # Leave-one-out from P16.
    for drop in P16_KEYS:
        w = dict(full)
        w[drop] = 0.0
        variants.append((f"P16-no{drop}", w))

    # Leave-two-out for low contribution / risk-management exploration.
    removable = list("ABCEGHLNPQ")
    for a, b in itertools.combinations(removable, 2):
        w = dict(full)
        w[a] = 0.0
        w[b] = 0.0
        variants.append((f"P16-no{a}{b}", w))
    return variants


def _score(summary, s75_summary, worst_floor):
    beats_avg = summary["avg_day"] > s75_summary["avg_day"]
    beats_min = summary["min_day"] > s75_summary["min_day"]
    streak_ok = summary["max_streak"] <= s75_summary["max_streak"]
    guard_ok = summary["worst_day"] >= worst_floor
    return (
        1 if (beats_avg and beats_min and streak_ok and guard_ok) else 0,
        1 if (beats_avg and streak_ok and guard_ok) else 0,
        round(summary["avg_day"], 4),
        round(summary["min_day"], 4),
        round(summary["worst_day"], 2),
        round(summary["min_pf"], 4),
        -summary["max_streak"],
    )


def _label(base_name, weights):
    parts = [base_name]
    for leg in ALLIN_KEYS:
        v = weights.get(leg, 0.0)
        if v:
            parts.append(f"{leg}x{v:g}")
    return "+".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="90,120,150,180")
    ap.add_argument("--cache-dir", default=os.path.join(ROOT_DIR, "tmp", "s72_cache"))
    ap.add_argument("--out", default="s76_champion_search.csv")
    ap.add_argument("--worst-floor", type=float, default=-1000.0)
    args = ap.parse_args()
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]

    pre_by_window = {}
    for days in windows:
        payload = _load_cache(args.cache_dir, days, DEFAULT_SPREAD)
        if payload is None:
            raise SystemExit(f"missing S72 cache for {days}d")
        demo_raw = _normalize_demo_raw(payload)
        allin_raw = _normalize_allin_raw(payload)
        pre = {}
        for leg, raw in {**demo_raw, **allin_raw}.items():
            pre[leg] = _simulate_leg(raw, _cfg_for_leg(leg))
        pre_by_window[days] = pre

    s75_rows = [_stats(pre_by_window[d], S75_WEIGHTS, d) for d in windows]
    s75_summary = _summary(s75_rows)

    # Wider than S75 grid, including values around the previous champion.
    w63_grid = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 16.0]
    w69_grid = [0.0, 8.0, 16.0, 20.0, 24.0, 28.0, 32.0, 36.0, 40.0, 48.0]
    w64_grid = [0.0, 1.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0]

    combos = []
    for base_name, base_weights in _base_variants():
        for w63, w69, w64 in itertools.product(w63_grid, w69_grid, w64_grid):
            if w63 == 0.0 and w69 == 0.0 and w64 == 0.0:
                continue
            weights = dict(base_weights)
            weights.update({"S63": w63, "S69": w69, "S64": w64})
            rows = [_stats(pre_by_window[d], weights, d) for d in windows]
            summary = _summary(rows)
            score = _score(summary, s75_summary, args.worst_floor)
            combos.append((base_name, weights, rows, summary, score))

    combos.sort(key=lambda x: x[4], reverse=True)

    fields = [
        "timestamp", "rank", "label", "score", "avg_day", "min_day", "min_pf",
        "max_streak", "worst_day", "max_lot", "max_leg_dd_pct", "skipped_by_cb",
        "days", "day", "daily_pf", "sharpe", "pos_day_pct", "window_streak",
        "window_worst_day", "best_day", "trade_units", "by_leg",
    ]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        # Include S75 baseline first.
        for r in s75_rows:
            w.writerow({
                "timestamp": ts,
                "rank": 0,
                "label": "S75_BASELINE",
                "score": "",
                "avg_day": round(s75_summary["avg_day"], 2),
                "min_day": round(s75_summary["min_day"], 2),
                "min_pf": round(s75_summary["min_pf"], 3),
                "max_streak": s75_summary["max_streak"],
                "worst_day": round(s75_summary["worst_day"], 2),
                "max_lot": round(s75_summary["max_lot"], 2),
                "max_leg_dd_pct": round(s75_summary["max_leg_dd_pct"], 2),
                "skipped_by_cb": s75_summary["skipped_by_cb"],
                "days": r["days"],
                "day": round(r["day"], 2),
                "daily_pf": round(r["daily_pf"], 3),
                "sharpe": r["sharpe"],
                "pos_day_pct": r["pos_day_pct"],
                "window_streak": r["max_streak"],
                "window_worst_day": round(r["worst_day"], 2),
                "best_day": round(r["best_day"], 2),
                "trade_units": round(r["trade_units"], 2),
                "by_leg": ";".join(f"{k}:{v:.2f}" for k, v in sorted(r["by_leg"].items())),
            })
        for rank, (base_name, weights, rows, summary, score) in enumerate(combos[:80], 1):
            label = _label(base_name, weights)
            for r in rows:
                w.writerow({
                    "timestamp": ts,
                    "rank": rank,
                    "label": label,
                    "score": score,
                    "avg_day": round(summary["avg_day"], 2),
                    "min_day": round(summary["min_day"], 2),
                    "min_pf": round(summary["min_pf"], 3),
                    "max_streak": summary["max_streak"],
                    "worst_day": round(summary["worst_day"], 2),
                    "max_lot": round(summary["max_lot"], 2),
                    "max_leg_dd_pct": round(summary["max_leg_dd_pct"], 2),
                    "skipped_by_cb": summary["skipped_by_cb"],
                    "days": r["days"],
                    "day": round(r["day"], 2),
                    "daily_pf": round(r["daily_pf"], 3),
                    "sharpe": r["sharpe"],
                    "pos_day_pct": r["pos_day_pct"],
                    "window_streak": r["max_streak"],
                    "window_worst_day": round(r["worst_day"], 2),
                    "best_day": round(r["best_day"], 2),
                    "trade_units": round(r["trade_units"], 2),
                    "by_leg": ";".join(f"{k}:{v:.2f}" for k, v in sorted(r["by_leg"].items())),
                })

    print(
        "S75 baseline: "
        f"avg$/d={s75_summary['avg_day']:.2f} min$/d={s75_summary['min_day']:.2f} "
        f"minPF={s75_summary['min_pf']:.2f} streak={s75_summary['max_streak']} "
        f"worst={s75_summary['worst_day']:.2f}"
    )
    print("Top S76 candidates:")
    for i, (base_name, weights, rows, summary, score) in enumerate(combos[:12], 1):
        print(
            f"{i:>2}. {_label(base_name, weights)} avg$/d={summary['avg_day']:.2f} "
            f"min$/d={summary['min_day']:.2f} minPF={summary['min_pf']:.2f} "
            f"streak={summary['max_streak']} worst={summary['worst_day']:.2f} score={score}"
        )
        print("  " + " | ".join(
            f"{r['days']}d {r['day']:.2f}/d PF={r['daily_pf']:.2f} st={r['max_streak']} "
            f"worst={r['worst_day']:.2f}" for r in rows
        ))
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
