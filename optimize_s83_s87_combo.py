"""
optimize_s83_s87_combo.py - Search S83 from S82 by adding S87 variants.

RESEARCH/BACKTEST-ONLY. No live bot wiring.

Uses the same portfolio sizing framework as P13/P16/S75/S76/S77/S81/S82:
    simulate_equity_substream(raw, cfg, START_EQUITY=1000)
per leg, then sums daily PnL across weighted legs.
"""

import argparse
import csv
import os
from datetime import datetime

import MetaTrader5 as mt5
import numpy as np

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
)
from sim_s62_backtest import _atr_series
from sim_s86_backtest import run_single as run_s86
from sim_s87_filter_s86 import S86_M15_STRICT, fetch_htf_bars
from strategy87 import build_closed_series, filter_trades


S82_WEIGHTS = {k: 1.0 for k in DEMO_KEYS + ALLIN_KEYS + ["S87_MAIN"]}
S82_WEIGHTS.update({"S63": 12.8, "S69": 22.1925, "S64": 13.875, "S87_MAIN": 33.55})
S83_WEIGHTS = dict(S82_WEIGHTS)
S83_WEIGHTS["S88_D1_INV_NO17"] = 14.43
S84_WEIGHTS = dict(S83_WEIGHTS)
S84_WEIGHTS["S89_D1_INV_NO17_RISK20"] = 10.0

S87_LEGS = {
    "S87_MAIN": ("D1_H12_TURN_follow", "D1_H12_TURN", "follow"),
    "S87_D1_LAST_INV": ("D1_LAST_inverse", "D1_LAST", "inverse"),
    "S87_D1_REV": ("D1_THEN_H12_REVERSAL_follow", "D1_THEN_H12_REVERSAL", "follow"),
    "S87_H12_TURN": ("H12_TURN_follow", "H12_TURN", "follow"),
    "S88_D1_INV_NO17": ("D1_LAST_inverse_no17", "D1_LAST", "inverse"),
    "S88_D1_INV_RISK10": ("D1_LAST_inverse_risk10", "D1_LAST", "inverse"),
    "S88_D1_INV_RATR12": ("D1_LAST_inverse_ratr12", "D1_LAST", "inverse"),
    "S89_D1_INV_NO17_RISK20": ("D1_LAST_inverse_no17_risk20", "D1_LAST", "inverse"),
    "S89_D1_INV_NO17_RATR18": ("D1_LAST_inverse_no17_ratr18", "D1_LAST", "inverse"),
    "S89_D1_INV_NO17_RATR20": ("D1_LAST_inverse_no17_ratr20", "D1_LAST", "inverse"),
}


def _frange(spec):
    start, stop, step = [float(x) for x in spec.split(":")]
    vals = []
    cur = start
    while cur <= stop + 1e-9:
        vals.append(round(cur, 4))
        cur += step
    return vals


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


def _run_s87_raws(days, spread):
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
    out = {}
    for leg, (_label, mode, relation) in S87_LEGS.items():
        tagged = []
        for t in filter_trades(raw, d1_series, h12_series, mode, relation=relation):
            if not _post_filter(leg, t):
                continue
            x = dict(t)
            x["leg"] = leg
            tagged.append(x)
        out[leg] = tagged
    return out


def _risk_atr(t):
    reason = str(t.get("reason", ""))
    marker = "riskATR="
    if marker not in reason:
        return 0.0
    try:
        return float(reason.split(marker, 1)[1].split()[0])
    except (ValueError, IndexError):
        return 0.0


def _post_filter(leg, t):
    if leg == "S88_D1_INV_NO17":
        hour = config.mt5_ts_to_bkk(int(t["fill_time_ts"])).hour
        return hour != 17
    if leg == "S88_D1_INV_RISK10":
        return float(t.get("risk_distance", 0.0)) <= 10.0
    if leg == "S88_D1_INV_RATR12":
        return _risk_atr(t) <= 1.2
    if leg == "S89_D1_INV_NO17_RISK20":
        hour = config.mt5_ts_to_bkk(int(t["fill_time_ts"])).hour
        return hour != 17 and float(t.get("risk_distance", 0.0)) <= 20.0
    if leg == "S89_D1_INV_NO17_RATR18":
        hour = config.mt5_ts_to_bkk(int(t["fill_time_ts"])).hour
        return hour != 17 and _risk_atr(t) <= 1.8
    if leg == "S89_D1_INV_NO17_RATR20":
        hour = config.mt5_ts_to_bkk(int(t["fill_time_ts"])).hour
        return hour != 17 and _risk_atr(t) <= 2.0
    return True


def _cfg_for_extra(leg):
    if leg in S87_LEGS:
        return S86_M15_STRICT
    return _cfg_for_leg(leg)


def _vector_pack(pre):
    days = sorted({d for _, _, by_day in pre.values() for d in by_day})
    arrays = {}
    for leg, (_, _, by_day) in pre.items():
        arrays[leg] = np.array([float(by_day.get(d, 0.0)) for d in days], dtype=float)
    eq = {leg: eq_stats for leg, (_twp, eq_stats, _by_day) in pre.items()}
    counts = {leg: len(twp) for leg, (twp, _eq_stats, _by_day) in pre.items()}
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


def _combined_daily(pack, weights):
    vals = None
    parts = {}
    for leg, weight in weights.items():
        if weight <= 0 or leg not in pack["arrays"]:
            continue
        arr = pack["arrays"][leg] * weight
        vals = arr if vals is None else vals + arr
        parts[leg] = arr
    if vals is None:
        vals = np.zeros(len(pack["days"]), dtype=float)
    return vals, parts


def _write_worst_day_audit(path, packs, windows, weights_by_label):
    fields = [
        "label", "days", "date", "total",
        "S87_MAIN", "S87_D1_LAST_INV", "S87_D1_REV", "S87_H12_TURN",
        "S88_D1_INV_NO17", "S88_D1_INV_RISK10", "S88_D1_INV_RATR12",
        "S89_D1_INV_NO17_RISK20", "S89_D1_INV_NO17_RATR18", "S89_D1_INV_NO17_RATR20",
        "demo_allin_total",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for label, weights in weights_by_label.items():
            for days in windows:
                pack = packs[days]
                vals, parts = _combined_daily(pack, weights)
                if len(vals) == 0:
                    continue
                idx = int(vals.argmin())
                s87_vals = {
                    leg: float(parts.get(leg, np.zeros(len(vals)))[idx])
                    for leg in S87_LEGS
                }
                demo_allin = float(vals[idx] - sum(s87_vals.values()))
                w.writerow({
                    "label": label,
                    "days": days,
                    "date": pack["days"][idx],
                    "total": round(float(vals[idx]), 4),
                    "S87_MAIN": round(s87_vals["S87_MAIN"], 4),
                    "S87_D1_LAST_INV": round(s87_vals["S87_D1_LAST_INV"], 4),
                    "S87_D1_REV": round(s87_vals["S87_D1_REV"], 4),
                    "S87_H12_TURN": round(s87_vals["S87_H12_TURN"], 4),
                    "S88_D1_INV_NO17": round(s87_vals["S88_D1_INV_NO17"], 4),
                    "S88_D1_INV_RISK10": round(s87_vals["S88_D1_INV_RISK10"], 4),
                    "S88_D1_INV_RATR12": round(s87_vals["S88_D1_INV_RATR12"], 4),
                    "S89_D1_INV_NO17_RISK20": round(s87_vals["S89_D1_INV_NO17_RISK20"], 4),
                    "S89_D1_INV_NO17_RATR18": round(s87_vals["S89_D1_INV_NO17_RATR18"], 4),
                    "S89_D1_INV_NO17_RATR20": round(s87_vals["S89_D1_INV_NO17_RATR20"], 4),
                    "demo_allin_total": round(demo_allin, 4),
                })


def _row(ts, rank, label, add_leg, add_weight, score, summary, r):
    return {
        "timestamp": ts,
        "rank": rank,
        "label": label,
        "add_leg": add_leg,
        "add_weight": add_weight,
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
    ap.add_argument("--out", default="s83_s87_combo_search.csv")
    ap.add_argument("--audit-out", default="s83_s87_worst_day_audit.csv")
    ap.add_argument("--floor", type=float, default=-1000.0)
    ap.add_argument("--max-streak", type=int, default=3)
    ap.add_argument("--wadd", default="0:20:0.1")
    ap.add_argument("--base", choices=["S82", "S83", "S84"], default="S82")
    ap.add_argument("--add-leg", default="", help="optional single extra leg to search")
    ap.add_argument("--top", type=int, default=160, help="number of ranked candidates to write/audit")
    args = ap.parse_args()
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    w_grid = _frange(args.wadd)

    if not config.mt5_initialize(mt5):
        raise SystemExit(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
    try:
        packs = {}
        for days in windows:
            payload = _load_cache(args.cache_dir, days, DEFAULT_SPREAD)
            if payload is None:
                raise SystemExit(f"missing S72 cache for {days}d")
            demo_raw = _normalize_demo_raw(payload)
            allin_raw = _normalize_allin_raw(payload)
            s87_raw = _run_s87_raws(days, DEFAULT_SPREAD)
            pre = {}
            for leg, raw in {**demo_raw, **allin_raw, **s87_raw}.items():
                pre[leg] = _simulate_leg(raw, _cfg_for_extra(leg))
            packs[days] = _vector_pack(pre)
    finally:
        mt5.shutdown()

    base_map = {"S82": S82_WEIGHTS, "S83": S83_WEIGHTS, "S84": S84_WEIGHTS}
    base_weights = dict(base_map[args.base])
    base_rows = [_window_stats(packs[d], base_weights, d) for d in windows]
    base_summary = _summary(base_rows)

    candidates = []
    add_legs = [k for k in S87_LEGS if k != "S87_MAIN" and base_weights.get(k, 0.0) <= 0]
    if args.add_leg:
        if args.add_leg not in S87_LEGS:
            raise SystemExit(f"unknown add leg: {args.add_leg}")
        add_legs = [args.add_leg]
    for add_leg in add_legs:
        for add_weight in w_grid:
            weights = dict(base_weights)
            weights[add_leg] = add_weight
            rows = [_window_stats(packs[d], weights, d) for d in windows]
            summary = _summary(rows)
            beats = (
                summary["avg_day"] > base_summary["avg_day"]
                and summary["min_day"] > base_summary["min_day"]
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
            label = f"{args.base}+{add_leg}x{add_weight:g}"
            candidates.append((score, add_leg, add_weight, label, rows, summary, beats))
    candidates.sort(key=lambda x: x[0], reverse=True)

    fields = [
        "timestamp", "rank", "label", "add_leg", "add_weight", "score",
        "avg_day", "min_day", "min_pf", "max_streak", "worst_day",
        "max_lot", "max_leg_dd_pct", "skipped_by_cb", "days", "day",
        "daily_pf", "window_streak", "window_worst_day", "best_day",
        "trade_units", "by_leg",
    ]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in base_rows:
            w.writerow(_row(ts, 0, f"{args.base}_BASELINE", "", "", "", base_summary, r))
        for rank, (score, add_leg, add_weight, label, rows, summary, beats) in enumerate(candidates[:args.top], 1):
            for r in rows:
                w.writerow(_row(ts, rank, label, add_leg, add_weight, score, summary, r))

    audit_weights = {f"{args.base}_BASELINE": dict(base_weights)}
    for score, add_leg, add_weight, label, _rows, cand_summary, _beats in candidates[:20]:
        weights = dict(base_weights)
        weights[add_leg] = add_weight
        audit_weights[label] = weights
    _write_worst_day_audit(args.audit_out, packs, windows, audit_weights)

    print(
        f"{args.base} baseline avg$/d={base_summary['avg_day']:.2f} min$/d={base_summary['min_day']:.2f} "
        f"PF={base_summary['min_pf']:.2f} st={base_summary['max_streak']} worst={base_summary['worst_day']:.2f}"
    )
    print("Top S83 S87-combo candidates:")
    for i, (score, add_leg, add_weight, label, rows, summary, beats) in enumerate(candidates[:20], 1):
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
    print(f"-> {os.path.abspath(args.audit_out)}")


if __name__ == "__main__":
    main()
