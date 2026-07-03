"""
optimize_s87_overlay_s81.py - Test S87-filtered S86 overlay above S81.

RESEARCH/BACKTEST-ONLY. No live bot wiring.

Uses the same portfolio sizing framework as P13/P16/S75/S76/S77/S81:
    simulate_equity_substream(raw, cfg, START_EQUITY=1000)
per leg, then sums daily PnL across weighted legs.
"""

import argparse
import csv
import os
from datetime import datetime

import MetaTrader5 as mt5

import config
import sim_s30_backtest as s30sim
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
from sim_s62_backtest import _atr_series
from sim_s86_backtest import run_single as run_s86
from sim_s87_filter_s86 import S86_M15_STRICT, fetch_htf_bars
from strategy87 import build_closed_series, filter_trades


S81_WEIGHTS = {k: 1.0 for k in DEMO_KEYS + ALLIN_KEYS + ["S87"]}
S81_WEIGHTS.update({"S63": 12.8, "S69": 22.1925, "S64": 13.875, "S87": 0.0})

S87_CANDIDATES = [
    ("D1_LAST_inverse", "D1_LAST", "inverse"),
    ("D1_H12_TURN_follow", "D1_H12_TURN", "follow"),
    ("D1_THEN_H12_REVERSAL_follow", "D1_THEN_H12_REVERSAL", "follow"),
    ("H12_TURN_follow", "H12_TURN", "follow"),
]


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


def _frange(spec):
    start, stop, step = [float(x) for x in spec.split(":")]
    vals = []
    cur = start
    while cur <= stop + 1e-9:
        vals.append(round(cur, 4))
        cur += step
    return vals


def _run_s87_raw(days, spread, mode, relation):
    cfg = dict(S86_M15_STRICT)
    bars = s30sim.fetch_bars(config.SYMBOL, cfg["ENTRY_TF"], days, extra_bars=760)
    d1_bars = fetch_htf_bars(config.SYMBOL, "D1", days, extra_bars=60)
    h12_bars = fetch_htf_bars(config.SYMBOL, "H12", days, extra_bars=120)
    if bars is None or d1_bars is None or h12_bars is None:
        raise RuntimeError(f"failed to fetch S87 bars for {days}d")
    cfg["_ATR14"] = _atr_series(bars, 14)
    cfg["_DT_BKK"] = [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]
    raw = run_s86(bars, cfg, days, spread)
    d1_series = build_closed_series(d1_bars, "D1")
    h12_series = build_closed_series(h12_bars, "H12")
    out = []
    for t in filter_trades(raw, d1_series, h12_series, mode, relation=relation):
        x = dict(t)
        x["leg"] = "S87"
        out.append(x)
    return out


def _cfg_for_extra(leg):
    if leg == "S87":
        return S86_M15_STRICT
    return _cfg_for_leg(leg)


def _row(ts, rank, label, cand, w87, score, summary, r):
    return {
        "timestamp": ts,
        "rank": rank,
        "label": label,
        "candidate": cand,
        "w87": w87,
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
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="90,120,150,180")
    ap.add_argument("--cache-dir", default=os.path.join(ROOT_DIR, "tmp", "s72_cache"))
    ap.add_argument("--out", default="s87_overlay_s81_search.csv")
    ap.add_argument("--floor", type=float, default=-1000.0)
    ap.add_argument("--max-streak", type=int, default=3)
    ap.add_argument("--w87", default="0:40:0.25")
    args = ap.parse_args()
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    w_grid = _frange(args.w87)

    if not config.mt5_initialize(mt5):
        raise SystemExit(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
    try:
        pre_by_candidate = {}
        for cand, mode, relation in S87_CANDIDATES:
            pre_by_window = {}
            for days in windows:
                payload = _load_cache(args.cache_dir, days, DEFAULT_SPREAD)
                if payload is None:
                    raise SystemExit(f"missing S72 cache for {days}d")
                demo_raw = _normalize_demo_raw(payload)
                allin_raw = _normalize_allin_raw(payload)
                s87_raw = _run_s87_raw(days, DEFAULT_SPREAD, mode, relation)
                pre = {}
                for leg, raw in {**demo_raw, **allin_raw, "S87": s87_raw}.items():
                    pre[leg] = _simulate_leg(raw, _cfg_for_extra(leg))
                pre_by_window[days] = pre
            pre_by_candidate[cand] = pre_by_window
    finally:
        mt5.shutdown()

    first_pre = next(iter(pre_by_candidate.values()))
    s81_rows = [_stats(first_pre[d], S81_WEIGHTS, d) for d in windows]
    s81_summary = _summary(s81_rows)

    candidates = []
    for cand, pre_by_window in pre_by_candidate.items():
        s87_only = {k: 0.0 for k in DEMO_KEYS + ALLIN_KEYS + ["S87"]}
        s87_only["S87"] = 1.0
        s87_rows = [_stats(pre_by_window[d], s87_only, d) for d in windows]
        candidates.append(((0, -1, -1, -99, -9, -9999), cand, "S87_ONLY", "", s87_rows, _summary(s87_rows), False))
        for w87 in w_grid:
            weights = dict(S81_WEIGHTS)
            weights["S87"] = w87
            rows = [_stats(pre_by_window[d], weights, d) for d in windows]
            summary = _summary(rows)
            beats = (
                summary["avg_day"] > s81_summary["avg_day"]
                and summary["min_day"] > s81_summary["min_day"]
                and summary["max_streak"] <= args.max_streak
                and summary["worst_day"] >= args.floor
            )
            score = (
                1 if beats else 0,
                round(summary["avg_day"], 6),
                round(summary["min_day"], 6),
                round(summary["worst_day"], 4),
                round(summary["min_pf"], 6),
                -summary["max_streak"],
            )
            label = f"S81+{cand}x{w87:g}"
            candidates.append((score, cand, label, w87, rows, summary, beats))
    candidates.sort(key=lambda x: x[0], reverse=True)

    fields = [
        "timestamp", "rank", "label", "candidate", "w87", "score",
        "avg_day", "min_day", "min_pf", "max_streak", "worst_day",
        "max_lot", "max_leg_dd_pct", "skipped_by_cb", "days", "day",
        "daily_pf", "window_streak", "window_worst_day", "best_day",
        "trade_units", "by_leg",
    ]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in s81_rows:
            w.writerow(_row(ts, 0, "S81_BASELINE", "", "", "", s81_summary, r))
        for rank, (score, cand, label, w87, rows, summary, beats) in enumerate(candidates[:120], 1):
            for r in rows:
                w.writerow(_row(ts, rank, label, cand, w87, score, summary, r))

    print(
        f"S81 baseline avg$/d={s81_summary['avg_day']:.2f} min$/d={s81_summary['min_day']:.2f} "
        f"PF={s81_summary['min_pf']:.2f} st={s81_summary['max_streak']} worst={s81_summary['worst_day']:.2f}"
    )
    print("Top S87 overlay candidates:")
    for i, (score, cand, label, w87, rows, summary, beats) in enumerate(candidates[:20], 1):
        print(
            f"{i:>2}. {label} avg$/d={summary['avg_day']:.2f} min$/d={summary['min_day']:.2f} "
            f"minPF={summary['min_pf']:.2f} st={summary['max_streak']} "
            f"worst={summary['worst_day']:.2f} beats={beats}"
        )
        print("  " + " | ".join(
            f"{r['days']}d {r['day']:.2f}/d PF={r['daily_pf']:.2f} "
            f"st={r['max_streak']} worst={r['worst_day']:.2f}" for r in rows
        ))
    print(f"\n-> {os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()
