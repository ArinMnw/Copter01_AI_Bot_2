"""
optimize_s82_with_s66.py - Add S66 FVG Ladder overlay above S81.

RESEARCH/BACKTEST-ONLY. No live bot wiring.

Uses the same sizing formula as P13/P16/S75/S76/S77/S81:
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
from sim_s66_backtest import run_single as run_s66
from strategy66 import S66_DEFAULTS


S81_WEIGHTS = {k: 1.0 for k in DEMO_KEYS + ALLIN_KEYS + ["S66"]}
S81_WEIGHTS.update({"S63": 12.8, "S69": 22.1925, "S64": 13.875, "S66": 0.0})

S66_A = dict(S66_DEFAULTS)
S66_A.update({
    "ENTRY_TF": "M5",
    "LOOKBACK": 80,
    "FVG_MIN_ATR": 0.04,
    "MIN_FVG_COUNT": 3,
    "ZONE_SELECT": "base",
    "TOUCH_TOL_ATR": 0.10,
    "MIN_BODY_ATR": 0.18,
    "MIN_BODY_RATIO": 0.35,
    "CLOSE_BEYOND_ZONE": True,
    "REQUIRE_LATEST_FAIL": False,
    "SL_ATR_MULT": 0.35,
    "TP_RR": 1.60,
})


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


def _cfg_for_extra(leg):
    if leg == "S66":
        return S66_A
    return _cfg_for_leg(leg)


def _tag(raw, leg):
    out = []
    for t in raw:
        x = dict(t)
        x["leg"] = leg
        out.append(x)
    return out


def _run_s66_raw(days, spread):
    if not config.mt5_initialize(mt5):
        raise SystemExit(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
    bars = s30sim.fetch_bars(config.SYMBOL, S66_A["ENTRY_TF"], days, extra_bars=620)
    mt5.shutdown()
    cfg = dict(S66_A)
    cfg["_ATR14"] = _atr_series(bars, 14)
    cfg["_DT_BKK"] = [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]
    return _tag(run_s66(bars, cfg, days, spread), "S66")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="90,120,150,180")
    ap.add_argument("--cache-dir", default=os.path.join(ROOT_DIR, "tmp", "s72_cache"))
    ap.add_argument("--out", default="s82_with_s66_search.csv")
    ap.add_argument("--floor", type=float, default=-1000.0)
    ap.add_argument("--max-streak", type=int, default=3)
    ap.add_argument("--w66", default="0:80:1")
    args = ap.parse_args()
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]

    start, stop, step = [float(x) for x in args.w66.split(":")]
    w66_grid = []
    cur = start
    while cur <= stop + 1e-9:
        w66_grid.append(round(cur, 4))
        cur += step

    pre_by_window = {}
    s66_raw_by_window = {}
    for days in windows:
        payload = _load_cache(args.cache_dir, days, DEFAULT_SPREAD)
        if payload is None:
            raise SystemExit(f"missing S72 cache for {days}d")
        demo_raw = _normalize_demo_raw(payload)
        allin_raw = _normalize_allin_raw(payload)
        s66_raw = s66_raw_by_window[days] = _run_s66_raw(days, DEFAULT_SPREAD)
        pre = {}
        for leg, raw in {**demo_raw, **allin_raw, "S66": s66_raw}.items():
            pre[leg] = _simulate_leg(raw, _cfg_for_extra(leg))
        pre_by_window[days] = pre

    s81_rows = [_stats(pre_by_window[d], S81_WEIGHTS, d) for d in windows]
    s81_summary = _summary(s81_rows)
    s66_only = {k: 0.0 for k in DEMO_KEYS + ALLIN_KEYS + ["S66"]}
    s66_only["S66"] = 1.0
    s66_rows = [_stats(pre_by_window[d], s66_only, d) for d in windows]
    s66_summary = _summary(s66_rows)

    candidates = []
    for w66 in w66_grid:
        weights = dict(S81_WEIGHTS)
        weights["S66"] = w66
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
        candidates.append((score, w66, rows, summary, beats))
    candidates.sort(key=lambda x: x[0], reverse=True)

    fields = [
        "timestamp", "rank", "label", "w66", "score", "avg_day", "min_day",
        "min_pf", "max_streak", "worst_day", "max_lot", "max_leg_dd_pct",
        "skipped_by_cb", "days", "day", "daily_pf", "window_streak",
        "window_worst_day", "best_day", "trade_units", "by_leg",
    ]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for label, rows, summary in [
            ("S81_BASELINE", s81_rows, s81_summary),
            ("S66_ONLY", s66_rows, s66_summary),
        ]:
            for r in rows:
                w.writerow(_row(ts, 0, label, "", "", summary, r))
        for rank, (score, w66, rows, summary, beats) in enumerate(candidates[:100], 1):
            label = f"S81+S66x{w66:g}"
            for r in rows:
                w.writerow(_row(ts, rank, label, w66, score, summary, r))

    print(
        f"S81 baseline avg$/d={s81_summary['avg_day']:.2f} min$/d={s81_summary['min_day']:.2f} "
        f"PF={s81_summary['min_pf']:.2f} st={s81_summary['max_streak']} worst={s81_summary['worst_day']:.2f}"
    )
    print(
        f"S66 only avg$/d={s66_summary['avg_day']:.2f} min$/d={s66_summary['min_day']:.2f} "
        f"PF={s66_summary['min_pf']:.2f} st={s66_summary['max_streak']} worst={s66_summary['worst_day']:.2f}"
    )
    print("Top S82 candidates:")
    for i, (score, w66, rows, summary, beats) in enumerate(candidates[:15], 1):
        print(
            f"{i:>2}. S81+S66x{w66:g} avg$/d={summary['avg_day']:.2f} "
            f"min$/d={summary['min_day']:.2f} minPF={summary['min_pf']:.2f} "
            f"st={summary['max_streak']} worst={summary['worst_day']:.2f} beats={beats}"
        )
        print("  " + " | ".join(
            f"{r['days']}d {r['day']:.2f}/d PF={r['daily_pf']:.2f} "
            f"st={r['max_streak']} worst={r['worst_day']:.2f}" for r in rows
        ))
    print(f"\n-> {args.out}")


def _row(ts, rank, label, w66, score, summary, r):
    return {
        "timestamp": ts,
        "rank": rank,
        "label": label,
        "w66": w66,
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


if __name__ == "__main__":
    main()
