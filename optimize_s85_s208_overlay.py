"""
optimize_s85_s208_overlay.py - Search S85 using S20.8 Small 2L/2H overlay above S84.

RESEARCH/BACKTEST-ONLY. No live bot wiring.

This runner converts S20.8 signals into the same raw-trade format used by the
champion portfolio framework:
    simulate_equity_substream(raw, cfg, START_EQUITY=1000)
per leg, then sums daily PnL across weighted legs.

Look-ahead guard:
- S20.8 sees only bars through closed bar j.
- Market fill is moved to bar j+1 open, not the signal bar close used by the
  older S20.8 scout.
"""

import argparse
import csv
import os
import sys
from datetime import datetime

import MetaTrader5 as mt5
import numpy as np

import config
import sim_s30_backtest as s30sim
from optimize_s72_vs_demo_portfolio import DEFAULT_SPREAD, ROOT_DIR, _load_cache
from optimize_s75_champion_formula import (
    _normalize_allin_raw,
    _normalize_demo_raw,
    _simulate_leg,
)
from optimize_s83_s87_combo import (
    S84_WEIGHTS,
    _cfg_for_extra,
    _combined_daily,
    _run_s87_raws,
    _summary,
    _vector_pack,
    _window_stats,
    _write_worst_day_audit,
)


S208_DIR = os.path.join(os.path.dirname(__file__), "strategy", "s20.8")
if S208_DIR not in sys.path:
    sys.path.insert(0, S208_DIR)

from strategy20_8 import _last_trigger, strategy_20_8  # noqa: E402


S208_CFG = {
    "RISK_PCT": 0.5,
    "DD_CONTROL": "circuit_breaker",
    "CONSEC_LOSS_TRIGGER": 3,
    "REDUCED_RISK_PCT": 0.35,
    "COOLDOWN_TRADES": 10,
}

TF_EXTRA_BARS = {
    "M1": 2200,
    "M5": 900,
    "M15": 520,
    "M30": 400,
}


class _S208Config:
    S20_8_ENABLED = True
    S20_8_POINTS_MULTIPLIER = 0.01
    S20_8_COMPOUNDING_ENABLED = False


def _frange(spec):
    start, stop, step = [float(x) for x in spec.split(":")]
    vals = []
    cur = start
    while cur <= stop + 1e-9:
        vals.append(round(cur, 4))
        cur += step
    return vals


def _cfg_for_leg(leg):
    if leg.startswith("S208_"):
        return S208_CFG
    return _cfg_for_extra(leg)


def _fetch_tf_bars(tf_name, days):
    extra = TF_EXTRA_BARS.get(tf_name, 500)
    return s30sim.fetch_bars(config.SYMBOL, tf_name, days, extra_bars=extra)


def _replay_s208_tf(bars, tf_name, spread):
    trades = []
    if bars is None or len(bars) < 150:
        return trades
    _last_trigger.clear()
    last_fire_idx = -100
    for j in range(130, len(bars) - 1):
        if j - last_fire_idx < 3:
            continue
        # Only closed bars through j are visible to the detector.
        rates_slice = bars[max(0, j - 130):j + 1]
        res = strategy_20_8(rates_slice, tf=tf_name, tf_name=tf_name, config=_S208Config)
        sig = res.get("signal")
        if sig not in ("BUY", "SELL"):
            continue
        fill_idx = j + 1
        fill_entry = float(bars[fill_idx]["open"])
        sl = float(res["sl"])
        tp = float(res["tp"])
        if sig == "BUY":
            if not (sl < fill_entry < tp):
                continue
            risk_distance = fill_entry - sl
        else:
            if not (tp < fill_entry < sl):
                continue
            risk_distance = sl - fill_entry
        if risk_distance <= 0:
            continue
        outcome = "OPEN"
        exit_price = None
        exit_idx = None
        for m in range(fill_idx, len(bars)):
            hi = float(bars[m]["high"])
            lw = float(bars[m]["low"])
            if sig == "BUY":
                if lw <= sl:
                    outcome, exit_price = "SL", sl
                elif hi >= tp:
                    outcome, exit_price = "TP", tp
            else:
                if hi >= sl:
                    outcome, exit_price = "SL", sl
                elif lw <= tp:
                    outcome, exit_price = "TP", tp
            if outcome != "OPEN":
                exit_idx = m
                break
        if outcome == "OPEN":
            continue
        last_fire_idx = j
        diff = (exit_price - fill_entry) if sig == "BUY" else (fill_entry - exit_price)
        trades.append({
            "leg": f"S208_{tf_name}",
            "tf": tf_name,
            "signal": sig,
            "outcome": outcome,
            "signal_time_ts": int(bars[j]["time"]),
            "fill_time_ts": int(bars[fill_idx]["time"]),
            "exit_time_ts": int(bars[exit_idx]["time"]),
            "entry": round(fill_entry, 2),
            "tp": round(tp, 2),
            "sl": round(sl, 2),
            "exit_price": round(exit_price, 2),
            "risk_distance": round(risk_distance, 4),
            "diff_usd_per_001lot": round(diff, 4),
            "spread": spread,
            "reason": "S20.8 closed-bar detect; fill=j+1 open",
        })
    return trades


def _run_s208_raws(days, spread, tfs):
    out = {}
    for tf_name in tfs:
        bars = _fetch_tf_bars(tf_name, days)
        if bars is None:
            out[f"S208_{tf_name}"] = []
        else:
            out[f"S208_{tf_name}"] = _replay_s208_tf(bars, tf_name, spread)
    return out


def _build_packs(windows, cache_dir, tfs):
    packs = {}
    for days in windows:
        payload = _load_cache(cache_dir, days, DEFAULT_SPREAD)
        if payload is None:
            raise SystemExit(f"missing S72 cache for {days}d")
        demo_raw = _normalize_demo_raw(payload)
        allin_raw = _normalize_allin_raw(payload)
        s87_raw = _run_s87_raws(days, DEFAULT_SPREAD)
        s208_raw = _run_s208_raws(days, DEFAULT_SPREAD, tfs)
        pre = {}
        for leg, raw in {**demo_raw, **allin_raw, **s87_raw, **s208_raw}.items():
            pre[leg] = _simulate_leg(raw, _cfg_for_leg(leg))
        packs[days] = _vector_pack(pre)
    return packs


def _floor_flags(summary, floors):
    return ";".join(
        f"{floor:g}:{'PASS' if summary['worst_day'] >= floor else 'FAIL'}"
        for floor in floors
    )


def _write_daily_audit(path, packs, windows, label, weights, legs):
    fields = ["label", "days", "date", "total"] + legs + ["other_total"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for days in windows:
            pack = packs[days]
            vals, parts = _combined_daily(pack, weights)
            zeros = np.zeros(len(vals))
            for idx, date in enumerate(pack["days"]):
                leg_vals = {leg: float(parts.get(leg, zeros)[idx]) for leg in legs}
                row = {
                    "label": label,
                    "days": days,
                    "date": date,
                    "total": round(float(vals[idx]), 4),
                    "other_total": round(float(vals[idx] - sum(leg_vals.values())), 4),
                }
                row.update({leg: round(v, 4) for leg, v in leg_vals.items()})
                w.writerow(row)


def _row(ts, rank, label, leg, weight, score, beats, floor_flags, summary, r):
    return {
        "timestamp": ts,
        "rank": rank,
        "label": label,
        "add_leg": leg,
        "add_weight": weight,
        "beats_s84": beats,
        "floor_flags": floor_flags,
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
    ap.add_argument("--tfs", default="M1,M5,M15,M30")
    ap.add_argument("--w", default="0:20:0.25")
    ap.add_argument("--base-s208-m1", type=float, default=0.0,
                    help="include S208_M1 in the baseline before searching other S208 legs")
    ap.add_argument("--floor", type=float, default=-1000.0)
    ap.add_argument("--floors", default="-700,-900,-973.16,-999.91,-1000")
    ap.add_argument("--max-streak", type=int, default=3)
    ap.add_argument("--out", default="s85_s208_overlay_search.csv")
    ap.add_argument("--audit-out", default="s85_s208_overlay_worst_day.csv")
    ap.add_argument("--daily-out", default="")
    ap.add_argument("--top", type=int, default=200)
    args = ap.parse_args()

    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    tfs = [x.strip() for x in args.tfs.split(",") if x.strip()]
    fetch_tfs = list(tfs)
    if args.base_s208_m1 > 0 and "M1" not in fetch_tfs:
        fetch_tfs.append("M1")
    legs = [f"S208_{tf}" for tf in tfs]
    w_grid = _frange(args.w)
    floors = [float(x.strip()) for x in args.floors.split(",") if x.strip()]

    if not config.mt5_initialize(mt5):
        raise SystemExit(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
    try:
        packs = _build_packs(windows, args.cache_dir, fetch_tfs)
    finally:
        mt5.shutdown()

    base_weights = dict(S84_WEIGHTS)
    base_label = "S84_BASELINE"
    if args.base_s208_m1 > 0:
        base_weights["S208_M1"] = args.base_s208_m1
        base_label = f"S85_BASELINE_S208_M1x{args.base_s208_m1:g}"
    base_rows = [_window_stats(packs[d], base_weights, d) for d in windows]
    base_summary = _summary(base_rows)

    candidates = []
    for leg in legs:
        for weight in w_grid:
            weights = dict(base_weights)
            weights[leg] = weight
            rows = [_window_stats(packs[d], weights, d) for d in windows]
            summary = _summary(rows)
            beats = (
                summary["avg_day"] > base_summary["avg_day"]
                and summary["min_day"] > base_summary["min_day"]
                and summary["max_streak"] <= args.max_streak
                and summary["worst_day"] >= args.floor
            )
            valid = summary["max_streak"] <= args.max_streak and summary["worst_day"] >= args.floor
            score = (
                1 if beats else 0,
                1 if valid else 0,
                round(summary["avg_day"], 6),
                round(summary["min_day"], 6),
                round(summary["worst_day"], 4),
                round(summary["min_pf"], 6),
                -summary["max_streak"],
            )
            label = f"{base_label}+{leg}x{weight:g}"
            candidates.append((score, leg, weight, label, rows, summary, beats, weights))
    candidates.sort(key=lambda x: x[0], reverse=True)

    fields = [
        "timestamp", "rank", "label", "add_leg", "add_weight", "beats_s84",
        "floor_flags", "score", "avg_day", "min_day", "min_pf", "max_streak",
        "worst_day", "max_lot", "max_leg_dd_pct", "skipped_by_cb", "days",
        "day", "daily_pf", "window_streak", "window_worst_day", "best_day",
        "trade_units", "by_leg",
    ]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in base_rows:
            w.writerow(_row(ts, 0, base_label, "", "", "", "", _floor_flags(base_summary, floors), base_summary, r))
        for rank, (score, leg, weight, label, rows, summary, beats, _weights) in enumerate(candidates[:args.top], 1):
            flags = _floor_flags(summary, floors)
            for r in rows:
                w.writerow(_row(ts, rank, label, leg, weight, score, beats, flags, summary, r))

    audit_weights = {base_label: dict(base_weights)}
    for _score, _leg, _weight, label, _rows, _cand_summary, _beats, weights in candidates[:20]:
        audit_weights[label] = weights
    _write_worst_day_audit(args.audit_out, packs, windows, audit_weights)
    if args.daily_out and candidates:
        _score, _leg, _weight, label, _rows, _cand_summary, _beats, weights = candidates[0]
        _write_daily_audit(args.daily_out, packs, windows, label, weights, legs)

    print(
        f"{base_label} avg$/d={base_summary['avg_day']:.2f} min$/d={base_summary['min_day']:.2f} "
        f"PF={base_summary['min_pf']:.2f} st={base_summary['max_streak']} worst={base_summary['worst_day']:.2f}"
    )
    print("S20.8 raw counts:")
    for days in windows:
        counts = ", ".join(f"{leg}={packs[days]['counts'].get(leg, 0)}" for leg in legs)
        print(f"  {days}d {counts}")
    print("Top S85 S20.8 candidates:")
    for i, (score, leg, weight, label, rows, summary, beats, _weights) in enumerate(candidates[:20], 1):
        print(
            f"{i:>2}. {label} avg$/d={summary['avg_day']:.2f} min$/d={summary['min_day']:.2f} "
            f"minPF={summary['min_pf']:.2f} st={summary['max_streak']} "
            f"worst={summary['worst_day']:.2f} beats={beats} floors={_floor_flags(summary, floors)}"
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
