"""
optimize_s77_champion_search.py - Fine search for a portfolio above S75/S76.

RESEARCH/BACKTEST-ONLY. No live bot wiring.

Uses the same sizing formula as P13/P16/S75/S76:
    simulate_equity_substream(raw, cfg, START_EQUITY=1000)
per leg, then sums daily PnL across weighted legs.
"""

import argparse
import csv
import heapq
import itertools
import os
from datetime import datetime

import numpy as np

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

S76_WEIGHTS = {k: 1.0 for k in DEMO_KEYS + ALLIN_KEYS}
S76_WEIGHTS.update({"S63": 10.0, "S69": 24.0, "S64": 12.0})


def _frange(start, stop, step):
    vals = []
    cur = start
    while cur <= stop + 1e-9:
        vals.append(round(cur, 4))
        cur += step
    return vals


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


def _base_variants(mode):
    variants = []
    full = {k: 1.0 for k in DEMO_KEYS + ALLIN_KEYS}
    for k in ALLIN_KEYS:
        full[k] = 0.0
    variants.append(("P16", full))
    if mode == "full":
        return variants

    for drop in P16_KEYS:
        w = dict(full)
        w[drop] = 0.0
        variants.append((f"P16-no{drop}", w))
    if mode == "loo":
        return variants

    removable = list("ABCEGHLNPQ")
    for a, b in itertools.combinations(removable, 2):
        w = dict(full)
        w[a] = 0.0
        w[b] = 0.0
        variants.append((f"P16-no{a}{b}", w))
    return variants


def _label(base_name, weights):
    parts = [base_name]
    for leg in ALLIN_KEYS:
        v = weights.get(leg, 0.0)
        if v:
            parts.append(f"{leg}x{v:g}")
    return "+".join(parts)


def _pf(vals):
    gross_win = float(vals[vals > 0].sum())
    gross_loss = float(-vals[vals <= 0].sum())
    if gross_loss <= 0:
        return 99.0 if gross_win > 0 else 0.0
    return gross_win / gross_loss


def _max_losing_streak(vals):
    streak = 0
    best = 0
    for v in vals:
        if v < 0:
            streak += 1
            if streak > best:
                best = streak
        else:
            streak = 0
    return best


def _vector_pack(pre):
    days = sorted({d for _, _, by_day in pre.values() for d in by_day})
    arrays = {}
    for leg, (_, _, by_day) in pre.items():
        arrays[leg] = np.array([float(by_day.get(d, 0.0)) for d in days], dtype=float)
    eq = {leg: eq_stats for leg, (twp, eq_stats, by_day) in pre.items()}
    trade_counts = {leg: len(twp) for leg, (twp, eq_stats, by_day) in pre.items()}
    return {"days": days, "arrays": arrays, "eq": eq, "trade_counts": trade_counts}


def _window_stats(pack, weights, days_count):
    vals = None
    by_leg = {}
    trade_units = 0.0
    max_lot = 0.0
    max_dd = 0.0
    skipped = 0
    for leg, weight in weights.items():
        if weight <= 0 or leg not in pack["arrays"]:
            continue
        arr = pack["arrays"][leg]
        vals = arr * weight if vals is None else vals + arr * weight
        by_leg[leg] = float(arr.sum() * weight)
        trade_units += pack["trade_counts"][leg] * weight
        eq = pack["eq"][leg]
        max_lot = max(max_lot, float(eq.get("lot_max", 0.0)))
        max_dd = max(max_dd, float(eq.get("max_dd_pct", 0.0)))
        skipped += int(eq.get("skipped_by_circuit_breaker", 0))

    if vals is None:
        vals = np.zeros(len(pack["days"]), dtype=float)
    total = float(vals.sum())
    return {
        "days": days_count,
        "trading_days": len(vals),
        "day": total / days_count if days_count else 0.0,
        "daily_pf": _pf(vals),
        "max_streak": _max_losing_streak(vals),
        "worst_day": float(vals.min()) if len(vals) else 0.0,
        "best_day": float(vals.max()) if len(vals) else 0.0,
        "max_lot": max_lot,
        "max_leg_dd_pct": max_dd,
        "skipped_by_cb": skipped,
        "trade_units": trade_units,
        "by_leg": by_leg,
    }


def _score(summary, s76_summary, floor):
    beats = (
        summary["avg_day"] > s76_summary["avg_day"]
        and summary["min_day"] > s76_summary["min_day"]
        and summary["max_streak"] <= s76_summary["max_streak"]
        and summary["worst_day"] >= floor
    )
    return (
        1 if beats else 0,
        1 if summary["avg_day"] > s76_summary["avg_day"] else 0,
        1 if summary["min_day"] > s76_summary["min_day"] else 0,
        1 if summary["max_streak"] <= s76_summary["max_streak"] else 0,
        round(summary["avg_day"], 6),
        round(summary["min_day"], 6),
        round(summary["worst_day"], 4),
        round(summary["min_pf"], 6),
        -summary["max_streak"],
    )


def _push_top(heaps, floors, base_name, weights, rows, summary, s76_summary, limit):
    for floor in floors:
        if summary["worst_day"] < floor:
            continue
        score = _score(summary, s76_summary, floor)
        item = (score, _label(base_name, weights), base_name, dict(weights), rows, dict(summary))
        heap = heaps[floor]
        if len(heap) < limit:
            heapq.heappush(heap, item)
        elif score > heap[0][0]:
            heapq.heapreplace(heap, item)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="90,120,150,180")
    ap.add_argument("--cache-dir", default=os.path.join(ROOT_DIR, "tmp", "s72_cache"))
    ap.add_argument("--out", default="s77_champion_search.csv")
    ap.add_argument("--top", type=int, default=120)
    ap.add_argument("--floors", default="-700,-900,-919.26,-973.16,-1000")
    ap.add_argument("--base-mode", choices=["full", "loo", "all"], default="loo")
    ap.add_argument("--w63", default="6:14:1")
    ap.add_argument("--w69", default="18:30:1")
    ap.add_argument("--w64", default="0:16:1")
    args = ap.parse_args()

    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    floors = [float(x.strip()) for x in args.floors.split(",") if x.strip()]

    pre_by_window = {}
    packs = {}
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
        packs[days] = _vector_pack(pre)

    s75_rows = [_stats(pre_by_window[d], S75_WEIGHTS, d) for d in windows]
    s76_rows = [_stats(pre_by_window[d], S76_WEIGHTS, d) for d in windows]
    s75_summary = _summary(s75_rows)
    s76_summary = _summary(s76_rows)

    def parse_grid(spec):
        start, stop, step = [float(x) for x in spec.split(":")]
        return _frange(start, stop, step)

    w63_grid = parse_grid(args.w63)
    w69_grid = parse_grid(args.w69)
    w64_grid = parse_grid(args.w64)

    heaps = {floor: [] for floor in floors}
    checked = 0
    for base_name, base_weights in _base_variants(args.base_mode):
        for w63, w69, w64 in itertools.product(w63_grid, w69_grid, w64_grid):
            weights = dict(base_weights)
            weights.update({"S63": w63, "S69": w69, "S64": w64})
            rows = [_window_stats(packs[d], weights, d) for d in windows]
            summary = _summary(rows)
            checked += 1
            _push_top(heaps, floors, base_name, weights, rows, summary, s76_summary, args.top)

    fields = [
        "timestamp", "floor", "rank", "label", "score", "avg_day", "min_day",
        "min_pf", "max_streak", "worst_day", "max_lot", "max_leg_dd_pct",
        "skipped_by_cb", "days", "day", "daily_pf", "window_streak",
        "window_worst_day", "best_day", "trade_units", "by_leg",
    ]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for label, rows, summary in [
            ("S75_BASELINE", s75_rows, s75_summary),
            ("S76_BASELINE", s76_rows, s76_summary),
        ]:
            for r in rows:
                writer.writerow({
                    "timestamp": ts,
                    "floor": "",
                    "rank": 0,
                    "label": label,
                    "score": "",
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
                    "window_streak": r["max_streak"],
                    "window_worst_day": round(r["worst_day"], 2),
                    "best_day": round(r["best_day"], 2),
                    "trade_units": round(r["trade_units"], 2),
                    "by_leg": ";".join(f"{k}:{v:.2f}" for k, v in sorted(r["by_leg"].items())),
                })

        for floor in floors:
            ranked = sorted(heaps[floor], key=lambda x: x[0], reverse=True)
            for rank, (score, label, base_name, weights, rows, summary) in enumerate(ranked, 1):
                for r in rows:
                    writer.writerow({
                        "timestamp": ts,
                        "floor": floor,
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
                        "window_streak": r["max_streak"],
                        "window_worst_day": round(r["worst_day"], 2),
                        "best_day": round(r["best_day"], 2),
                        "trade_units": round(r["trade_units"], 2),
                        "by_leg": ";".join(f"{k}:{v:.2f}" for k, v in sorted(r["by_leg"].items())),
                    })

    print(
        "Baselines: "
        f"S75 avg$/d={s75_summary['avg_day']:.2f} min$/d={s75_summary['min_day']:.2f} "
        f"PF={s75_summary['min_pf']:.2f} st={s75_summary['max_streak']} worst={s75_summary['worst_day']:.2f}; "
        f"S76 avg$/d={s76_summary['avg_day']:.2f} min$/d={s76_summary['min_day']:.2f} "
        f"PF={s76_summary['min_pf']:.2f} st={s76_summary['max_streak']} worst={s76_summary['worst_day']:.2f}"
    )
    print(f"Checked {checked:,} combinations.")
    for floor in floors:
        ranked = sorted(heaps[floor], key=lambda x: x[0], reverse=True)
        print(f"\nTop S77 candidates floor {floor:g}:")
        for i, (score, label, base_name, weights, rows, summary) in enumerate(ranked[:10], 1):
            print(
                f"{i:>2}. {label} avg$/d={summary['avg_day']:.2f} "
                f"min$/d={summary['min_day']:.2f} minPF={summary['min_pf']:.2f} "
                f"streak={summary['max_streak']} worst={summary['worst_day']:.2f} score={score}"
            )
            print("  " + " | ".join(
                f"{r['days']}d {r['day']:.2f}/d PF={r['daily_pf']:.2f} "
                f"st={r['max_streak']} worst={r['worst_day']:.2f}" for r in rows
            ))
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
