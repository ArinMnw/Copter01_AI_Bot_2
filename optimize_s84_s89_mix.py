"""
optimize_s84_s89_mix.py - Search S84 by rebalancing S88/S89 above S82/S83.

RESEARCH/BACKTEST-ONLY. No live bot wiring.

Uses the same portfolio sizing framework as S75/S76/S77/S81/S82/S83:
    simulate_equity_substream(raw, cfg, START_EQUITY=1000)
per leg, then sums daily PnL across weighted legs.
"""

import argparse
import csv
import os
from datetime import datetime

import MetaTrader5 as mt5

import config
from optimize_s72_vs_demo_portfolio import DEFAULT_SPREAD, ROOT_DIR, _load_cache
from optimize_s75_champion_formula import (
    _normalize_allin_raw,
    _normalize_demo_raw,
    _simulate_leg,
)
from optimize_s83_s87_combo import (
    S82_WEIGHTS,
    S83_WEIGHTS,
    S87_LEGS,
    _cfg_for_extra,
    _combined_daily,
    _frange,
    _row,
    _run_s87_raws,
    _summary,
    _vector_pack,
    _window_stats,
    _write_worst_day_audit,
)


def _build_packs(windows, cache_dir):
    packs = {}
    for days in windows:
        payload = _load_cache(cache_dir, days, DEFAULT_SPREAD)
        if payload is None:
            raise SystemExit(f"missing S72 cache for {days}d")
        demo_raw = _normalize_demo_raw(payload)
        allin_raw = _normalize_allin_raw(payload)
        s87_raw = _run_s87_raws(days, DEFAULT_SPREAD)
        pre = {}
        for leg, raw in {**demo_raw, **allin_raw, **s87_raw}.items():
            pre[leg] = _simulate_leg(raw, _cfg_for_extra(leg))
        packs[days] = _vector_pack(pre)
    return packs


def _candidate_rows(packs, windows, weights):
    rows = [_window_stats(packs[d], weights, d) for d in windows]
    return rows, _summary(rows)


def _floor_flags(summary, floors):
    return ";".join(
        f"{floor:g}:{'PASS' if summary['worst_day'] >= floor else 'FAIL'}"
        for floor in floors
    )


def _write_daily_audit(path, packs, windows, label, weights):
    fields = ["label", "days", "date", "total"] + sorted(S87_LEGS) + ["demo_allin_total"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for days in windows:
            pack = packs[days]
            vals, parts = _combined_daily(pack, weights)
            for idx, date in enumerate(pack["days"]):
                s87_vals = {
                    leg: float(parts.get(leg, [0.0] * len(vals))[idx])
                    for leg in S87_LEGS
                }
                demo_allin = float(vals[idx] - sum(s87_vals.values()))
                row = {
                    "label": label,
                    "days": days,
                    "date": date,
                    "total": round(float(vals[idx]), 4),
                    "demo_allin_total": round(demo_allin, 4),
                }
                row.update({leg: round(value, 4) for leg, value in s87_vals.items()})
                w.writerow(row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="90,120,150,180")
    ap.add_argument("--cache-dir", default=os.path.join(ROOT_DIR, "tmp", "s72_cache"))
    ap.add_argument("--out", default="s84_s89_mix_search.csv")
    ap.add_argument("--audit-out", default="s84_s89_mix_worst_day_audit.csv")
    ap.add_argument("--daily-out", default="")
    ap.add_argument("--floor", type=float, default=-1000.0)
    ap.add_argument("--floors", default="-700,-900,-973.16,-999.91,-1000")
    ap.add_argument("--max-streak", type=int, default=3)
    ap.add_argument("--base", choices=["S82", "S83"], default="S82")
    ap.add_argument("--leg-a", default="S88_D1_INV_NO17")
    ap.add_argument("--leg-b", default="S89_D1_INV_NO17_RISK20")
    ap.add_argument("--wa", default="8:14.5:0.25")
    ap.add_argument("--wb", default="0:40:0.25")
    ap.add_argument("--top", type=int, default=200)
    args = ap.parse_args()

    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    floors = [float(x.strip()) for x in args.floors.split(",") if x.strip()]
    wa_grid = _frange(args.wa)
    wb_grid = _frange(args.wb)
    for leg in (args.leg_a, args.leg_b):
        if leg not in S87_LEGS:
            raise SystemExit(f"unknown leg: {leg}")

    if not config.mt5_initialize(mt5):
        raise SystemExit(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
    try:
        packs = _build_packs(windows, args.cache_dir)
    finally:
        mt5.shutdown()

    base_weights = dict(S83_WEIGHTS if args.base == "S83" else S82_WEIGHTS)
    # For a rebalance search from S82, leg-a/leg-b are controlled by the grid.
    base_rows, base_summary = _candidate_rows(
        packs, windows, S83_WEIGHTS if args.base == "S83" else S82_WEIGHTS
    )
    champion_rows, champion_summary = _candidate_rows(packs, windows, S83_WEIGHTS)

    candidates = []
    for wa in wa_grid:
        for wb in wb_grid:
            weights = dict(base_weights)
            weights[args.leg_a] = wa
            weights[args.leg_b] = wb
            rows, summary = _candidate_rows(packs, windows, weights)
            beats_s83 = (
                summary["avg_day"] > champion_summary["avg_day"]
                and summary["min_day"] > champion_summary["min_day"]
                and summary["max_streak"] <= args.max_streak
                and summary["worst_day"] >= args.floor
            )
            valid = summary["max_streak"] <= args.max_streak and summary["worst_day"] >= args.floor
            score = (
                1 if beats_s83 else 0,
                1 if valid else 0,
                round(summary["avg_day"], 6),
                round(summary["min_day"], 6),
                round(summary["worst_day"], 4),
                round(summary["min_pf"], 6),
                -summary["max_streak"],
            )
            label = f"{args.base}+{args.leg_a}x{wa:g}+{args.leg_b}x{wb:g}"
            candidates.append((score, wa, wb, label, rows, summary, beats_s83, weights))
    candidates.sort(key=lambda x: x[0], reverse=True)

    fields = [
        "timestamp", "rank", "label", "add_leg", "add_weight", "leg_a", "weight_a",
        "leg_b", "weight_b", "beats_s83", "floor_flags", "score",
        "avg_day", "min_day", "min_pf", "max_streak", "worst_day",
        "max_lot", "max_leg_dd_pct", "skipped_by_cb", "days", "day",
        "daily_pf", "window_streak", "window_worst_day", "best_day",
        "trade_units", "by_leg",
    ]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for label, rows, summary in (
            (f"{args.base}_BASELINE", base_rows, base_summary),
            ("S83_CHAMPION", champion_rows, champion_summary),
        ):
            for r in rows:
                row = _row(ts, 0, label, "", "", "", summary, r)
                row.update({
                    "leg_a": "",
                    "weight_a": "",
                    "leg_b": "",
                    "weight_b": "",
                    "beats_s83": "",
                    "floor_flags": _floor_flags(summary, floors),
                })
                w.writerow(row)
        for rank, (score, wa, wb, label, rows, summary, beats_s83, _weights) in enumerate(candidates[:args.top], 1):
            for r in rows:
                row = _row(ts, rank, label, f"{args.leg_a}+{args.leg_b}", f"{wa:g}+{wb:g}", score, summary, r)
                row.update({
                    "leg_a": args.leg_a,
                    "weight_a": wa,
                    "leg_b": args.leg_b,
                    "weight_b": wb,
                    "beats_s83": beats_s83,
                    "floor_flags": _floor_flags(summary, floors),
                })
                w.writerow(row)

    audit_weights = {
        f"{args.base}_BASELINE": dict(base_weights),
        "S83_CHAMPION": dict(S83_WEIGHTS),
    }
    for _score, _wa, _wb, label, _rows, _summary, _beats_s83, weights in candidates[:20]:
        audit_weights[label] = weights
    _write_worst_day_audit(args.audit_out, packs, windows, audit_weights)

    best = candidates[0]
    if args.daily_out:
        _score, _wa, _wb, label, _rows, _summary, _beats_s83, weights = best
        _write_daily_audit(args.daily_out, packs, windows, label, weights)

    print(
        f"S83 champion avg$/d={champion_summary['avg_day']:.2f} min$/d={champion_summary['min_day']:.2f} "
        f"PF={champion_summary['min_pf']:.2f} st={champion_summary['max_streak']} "
        f"worst={champion_summary['worst_day']:.2f}"
    )
    print(f"Top S84 mix candidates ({args.leg_a} + {args.leg_b}):")
    for i, (score, wa, wb, label, rows, summary, beats_s83, _weights) in enumerate(candidates[:20], 1):
        print(
            f"{i:>2}. {label} avg$/d={summary['avg_day']:.2f} min$/d={summary['min_day']:.2f} "
            f"minPF={summary['min_pf']:.2f} st={summary['max_streak']} "
            f"worst={summary['worst_day']:.2f} beats_s83={beats_s83} floors={_floor_flags(summary, floors)}"
        )
        print("  " + " | ".join(
            f"{r['days']}d {r['day']:.2f}/d PF={r['daily_pf']:.2f} "
            f"st={r['max_streak']} worst={r['worst_day']:.2f}" for r in rows
        ))
    print(f"\n-> {os.path.abspath(args.out)}")
    print(f"-> {os.path.abspath(args.audit_out)}")
    if args.daily_out:
        print(f"-> {os.path.abspath(args.daily_out)}")


if __name__ == "__main__":
    main()
