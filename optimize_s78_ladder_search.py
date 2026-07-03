"""
optimize_s78_ladder_search.py - Continue champion search from S77.

RESEARCH/BACKTEST-ONLY. No live bot wiring.

Uses the same sizing formula as P13/P16/S75/S76/S77:
    simulate_equity_substream(raw, cfg, START_EQUITY=1000)
per leg, then sums daily PnL across weighted legs.
"""

import argparse
import csv
import itertools
import os
from datetime import datetime

import numpy as np

from optimize_s72_vs_demo_portfolio import DEFAULT_SPREAD, ROOT_DIR, _load_cache
from optimize_s75_champion_formula import (
    ALLIN_KEYS,
    DEMO_KEYS,
    _cfg_for_leg,
    _normalize_allin_raw,
    _normalize_demo_raw,
    _simulate_leg,
    _stats,
)


BASELINES = {
    "S75": {"S63": 8.0, "S69": 24.0, "S64": 8.0},
    "S76": {"S63": 10.0, "S69": 24.0, "S64": 12.0},
    "S77": {"S63": 11.75, "S69": 22.25, "S64": 13.25},
    "S78": {"S63": 12.5, "S69": 22.25, "S64": 13.75},
    "S79": {"S63": 12.625, "S69": 22.25, "S64": 13.875},
    "S80": {"S63": 12.6875, "S69": 22.25, "S64": 13.875},
    "S81": {"S63": 12.8, "S69": 22.1925, "S64": 13.875},
}


def _weights(overlays):
    out = {k: 1.0 for k in DEMO_KEYS + ALLIN_KEYS}
    out.update(overlays)
    return out


def _frange(spec):
    start, stop, step = [float(x) for x in spec.split(":")]
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
            best = max(best, streak)
        else:
            streak = 0
    return best


def _vector_pack(pre):
    days = sorted({d for _, _, by_day in pre.values() for d in by_day})
    arrays = {}
    for leg, (_, _, by_day) in pre.items():
        arrays[leg] = np.array([float(by_day.get(d, 0.0)) for d in days], dtype=float)
    eq = {leg: eq_stats for leg, (twp, eq_stats, by_day) in pre.items()}
    counts = {leg: len(twp) for leg, (twp, eq_stats, by_day) in pre.items()}
    return {"days": days, "arrays": arrays, "eq": eq, "counts": counts}


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
        trade_units += pack["counts"][leg] * weight
        eq = pack["eq"][leg]
        max_lot = max(max_lot, float(eq.get("lot_max", 0.0)))
        max_dd = max(max_dd, float(eq.get("max_dd_pct", 0.0)))
        skipped += int(eq.get("skipped_by_circuit_breaker", 0))

    if vals is None:
        vals = np.zeros(len(pack["days"]), dtype=float)
    return {
        "days": days_count,
        "day": float(vals.sum()) / days_count if days_count else 0.0,
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


def _label(prefix, overlays):
    return (
        f"{prefix}=P16+S63x{overlays['S63']:g}"
        f"+S69x{overlays['S69']:g}+S64x{overlays['S64']:g}"
    )


def _score(summary):
    return (
        round(summary["avg_day"], 6),
        round(summary["min_day"], 6),
        round(summary["worst_day"], 4),
        round(summary["min_pf"], 6),
        -summary["max_streak"],
    )


def _beats(candidate, baseline, floor, max_streak):
    return (
        candidate["avg_day"] > baseline["avg_day"]
        and candidate["min_day"] > baseline["min_day"]
        and candidate["max_streak"] <= max_streak
        and candidate["worst_day"] >= floor
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="90,120,150,180")
    ap.add_argument("--cache-dir", default=os.path.join(ROOT_DIR, "tmp", "s72_cache"))
    ap.add_argument("--out", default="s78_ladder_search.csv")
    ap.add_argument("--start", choices=sorted(BASELINES), default="S77")
    ap.add_argument("--first-id", type=int, default=78)
    ap.add_argument("--target-day", type=float, default=1000.0)
    ap.add_argument("--floor", type=float, default=-1000.0)
    ap.add_argument("--max-streak", type=int, default=3)
    ap.add_argument("--top", type=int, default=80)
    ap.add_argument("--w63", default="8:18:0.25")
    ap.add_argument("--w69", default="18:28:0.25")
    ap.add_argument("--w64", default="8:18:0.25")
    args = ap.parse_args()

    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    grids = {
        "S63": _frange(args.w63),
        "S69": _frange(args.w69),
        "S64": _frange(args.w64),
    }

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

    baseline_rows = {}
    baseline_summaries = {}
    for name, overlays in BASELINES.items():
        rows = [_stats(pre_by_window[d], _weights(overlays), d) for d in windows]
        baseline_rows[name] = rows
        baseline_summaries[name] = _summary(rows)

    start_overlays = dict(BASELINES[args.start])
    current_name = args.start
    current_summary = baseline_summaries[current_name]
    ladder = []
    top = []
    checked = 0

    for w63, w69, w64 in itertools.product(grids["S63"], grids["S69"], grids["S64"]):
        overlays = {"S63": w63, "S69": w69, "S64": w64}
        rows = [_window_stats(packs[d], _weights(overlays), d) for d in windows]
        summary = _summary(rows)
        checked += 1
        if summary["max_streak"] <= args.max_streak and summary["worst_day"] >= args.floor:
            item = (_score(summary), overlays, rows, summary)
            top.append(item)

    top.sort(key=lambda x: x[0], reverse=True)
    top = top[: args.top]

    best = None
    for score, overlays, rows, summary in top:
        if _beats(summary, current_summary, args.floor, args.max_streak):
            best = (overlays, rows, summary)
            break

    if best is not None:
        overlays, rows, summary = best
        ladder.append((f"S{args.first_id}", overlays, rows, summary))
        current_name = f"S{args.first_id}"
        current_summary = summary
        start_overlays = overlays

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fields = [
        "timestamp", "kind", "rank", "label", "avg_day", "min_day", "min_pf",
        "max_streak", "worst_day", "max_lot", "max_leg_dd_pct", "skipped_by_cb",
        "days", "day", "daily_pf", "window_streak", "window_worst_day",
        "best_day", "trade_units", "by_leg",
    ]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()

        for name in ["S75", "S76", "S77", "S78", "S79", "S80", "S81"]:
            summary = baseline_summaries[name]
            for r in baseline_rows[name]:
                w.writerow(_row(ts, "baseline", 0, _label(name, BASELINES[name]), summary, r))

        for rank, (score, overlays, rows, summary) in enumerate(top, 1):
            label = _label("CAND", overlays)
            for r in rows:
                w.writerow(_row(ts, "candidate", rank, label, summary, r))

        for rank, (name, overlays, rows, summary) in enumerate(ladder, 1):
            for r in rows:
                w.writerow(_row(ts, "ladder", rank, _label(name, overlays), summary, r))

    print(
        f"Baselines: S75 avg={baseline_summaries['S75']['avg_day']:.2f} "
        f"min={baseline_summaries['S75']['min_day']:.2f}; "
        f"S76 avg={baseline_summaries['S76']['avg_day']:.2f} "
        f"min={baseline_summaries['S76']['min_day']:.2f}; "
        f"S77 avg={baseline_summaries['S77']['avg_day']:.2f} "
        f"min={baseline_summaries['S77']['min_day']:.2f}; "
        f"S78 avg={baseline_summaries['S78']['avg_day']:.2f} "
        f"min={baseline_summaries['S78']['min_day']:.2f}; "
        f"S79 avg={baseline_summaries['S79']['avg_day']:.2f} "
        f"min={baseline_summaries['S79']['min_day']:.2f}; "
        f"S80 avg={baseline_summaries['S80']['avg_day']:.2f} "
        f"min={baseline_summaries['S80']['min_day']:.2f}; "
        f"S81 avg={baseline_summaries['S81']['avg_day']:.2f} "
        f"min={baseline_summaries['S81']['min_day']:.2f}"
    )
    print(f"Checked {checked:,} combos under floor {args.floor:g}, max streak {args.max_streak}.")
    if ladder:
        name, overlays, rows, summary = ladder[-1]
        print(
            f"{name} found: {_label(name, overlays)} avg$/d={summary['avg_day']:.2f} "
            f"min$/d={summary['min_day']:.2f} minPF={summary['min_pf']:.2f} "
            f"streak={summary['max_streak']} worst={summary['worst_day']:.2f}"
        )
        print("  " + " | ".join(
            f"{r['days']}d {r['day']:.2f}/d PF={r['daily_pf']:.2f} "
            f"st={r['max_streak']} worst={r['worst_day']:.2f}" for r in rows
        ))
        if summary["avg_day"] < args.target_day:
            print(
                f"Target {args.target_day:.2f}/day not reached. "
                "Current S63/S69/S64 reweight space needs new overlay/generator for the next jump."
            )
    else:
        print(
            f"No candidate beat {args.start} within this grid/floor. "
            "Need wider grid, looser floor, or a new raw-trade overlay."
        )

    print("\nTop valid candidates:")
    for i, (score, overlays, rows, summary) in enumerate(top[:12], 1):
        print(
            f"{i:>2}. {_label('CAND', overlays)} avg$/d={summary['avg_day']:.2f} "
            f"min$/d={summary['min_day']:.2f} minPF={summary['min_pf']:.2f} "
            f"streak={summary['max_streak']} worst={summary['worst_day']:.2f}"
        )
    print(f"\n-> {args.out}")


def _row(ts, kind, rank, label, summary, r):
    return {
        "timestamp": ts,
        "kind": kind,
        "rank": rank,
        "label": label,
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
    }


if __name__ == "__main__":
    main()
