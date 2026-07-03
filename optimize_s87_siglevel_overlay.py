"""
optimize_s87_siglevel_overlay.py - Search S87 using Significant Level Rejection overlay above S86.

RESEARCH/BACKTEST-ONLY. No live bot wiring.

This runner reuses the champion portfolio framework:
    simulate_equity_substream(raw, cfg, START_EQUITY=1000)
per leg, then sums daily PnL across weighted legs.

Look-ahead guard:
- Significant-level signals are detected from completed bar j only.
- Market fill is forced to bar j+1 open by sim_s85_backtest.replay85.
- Exit replay starts after that next-open fill and checks SL before TP on
  ambiguous same-bar touches.
"""

import argparse
import csv
import itertools
import os
from datetime import datetime

import MetaTrader5 as mt5
import numpy as np

import config
import sim_s30_backtest as s30sim
from optimize_s72_vs_demo_portfolio import DEFAULT_SPREAD, ROOT_DIR
from optimize_s75_champion_formula import _simulate_leg
from optimize_s83_s87_combo import (
    S84_WEIGHTS,
    _combined_daily,
    _summary,
    _window_stats,
)
from optimize_s85_s208_overlay import S208_CFG
from optimize_s86_s2010_overlay import S2010_CFG, _build_packs as _build_s86_packs
from sim_s62_backtest import _atr_series
from sim_s85_backtest import run_single as run_siglevel
from strategy85 import S85_DEFAULTS


SIGLEVEL_CFG = {
    "RISK_PCT": 0.5,
    "DD_CONTROL": "circuit_breaker",
    "CONSEC_LOSS_TRIGGER": 3,
    "REDUCED_RISK_PCT": 0.35,
    "COOLDOWN_TRADES": 10,
}

TF_EXTRA_BARS = {
    "M1": 2600,
    "M5": 1100,
    "M15": 700,
    "M30": 520,
    "H1": 420,
}


def _frange(spec):
    start, stop, step = [float(x) for x in spec.split(":")]
    vals = []
    cur = start
    while cur <= stop + 1e-9:
        vals.append(round(cur, 4))
        cur += step
    return vals


def _grid(preset):
    if preset == "micro":
        return (
            ["M5", "M15", "M30"],
            [72, 96],
            [8, 12],
            [0.08, 0.12],
            [0.04, 0.06],
            [0.18, 0.24],
            [0.8, 1.0],
            [False],
            [True],
            [True, False],
            [12],
            [0.8, 1.2],
            [0.25, 0.40],
            [1.0, 1.4],
        )
    if preset == "tiny":
        return (
            ["M5", "M15", "M30", "H1"],
            [48, 72, 96, 144],
            [5, 8, 12],
            [0.06, 0.12, 0.20],
            [0.03, 0.08, 0.14],
            [0.14, 0.24, 0.36],
            [0.6, 1.0, 1.4],
            [True, False],
            [True],
            [True, False],
            [10, 16],
            [0.6, 1.0, 1.5],
            [0.20, 0.35, 0.50],
            [0.9, 1.2, 1.6],
        )
    raise ValueError(preset)


def _cfg_label(cfg):
    return (
        f"S85SIG_{cfg['ENTRY_TF']}_lb{cfg['LOOKBACK']}_age{cfg['MIN_LEVEL_AGE']}"
        f"_t{cfg['TOUCH_TOL_ATR']:g}_a{cfg['CLOSE_AWAY_ATR']:g}"
        f"_w{cfg['MIN_REJECT_WICK_ATR']:g}_wb{cfg['WICK_BODY_MULT']:g}"
        f"_dj{int(cfg['USE_DOJI_LEVELS'])}_pv{int(cfg['USE_PIVOT_LEVELS'])}"
        f"_tr{int(cfg['REQUIRE_TREND_INTO_LEVEL'])}_tl{cfg['TREND_LOOKBACK']}"
        f"_tm{cfg['TREND_MIN_ATR']:g}_sl{cfg['SL_ATR_MULT']:g}_rr{cfg['TP_RR']:g}"
    )


def _make_cfg(vals):
    tf, lb, age, touch, away, wick, wickbody, doji, pivot, trend, tlb, tmin, slmult, rr = vals
    cfg = dict(S85_DEFAULTS)
    cfg.update(SIGLEVEL_CFG)
    cfg.update({
        "ENTRY_TF": tf,
        "LOOKBACK": lb,
        "MIN_LEVEL_AGE": age,
        "TOUCH_TOL_ATR": touch,
        "CLOSE_AWAY_ATR": away,
        "MIN_REJECT_WICK_ATR": wick,
        "WICK_BODY_MULT": wickbody,
        "USE_DOJI_LEVELS": doji,
        "USE_PIVOT_LEVELS": pivot,
        "REQUIRE_TREND_INTO_LEVEL": trend,
        "TREND_LOOKBACK": tlb,
        "TREND_MIN_ATR": tmin,
        "SL_ATR_MULT": slmult,
        "TP_RR": rr,
    })
    return cfg


def _fetch_tf_bars(tf_name, days):
    return s30sim.fetch_bars(config.SYMBOL, tf_name, days, extra_bars=TF_EXTRA_BARS.get(tf_name, 700))


def _base_weights():
    weights = dict(S84_WEIGHTS)
    weights["S208_M1"] = 39.33
    weights["S2010_M30_FSP"] = 11.73
    return weights


def _pack_with_siglevel(pack, label, twp, eq, by_day):
    arr = np.array([float(by_day.get(d, 0.0)) for d in pack["days"]], dtype=float)
    out = {
        "days": pack["days"],
        "arrays": dict(pack["arrays"]),
        "eq": dict(pack["eq"]),
        "counts": dict(pack["counts"]),
    }
    out["arrays"][label] = arr
    out["eq"][label] = eq
    out["counts"][label] = len(twp)
    return out


def _floor_flags(summary, floors):
    return ";".join(
        f"{floor:g}:{'PASS' if summary['worst_day'] >= floor else 'FAIL'}"
        for floor in floors
    )


def _row(ts, rank, label, weight, score, beats, floor_flags, summary, r):
    return {
        "timestamp": ts,
        "rank": rank,
        "label": label,
        "add_weight": weight,
        "beats_s86": beats,
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


def _write_worst_day_audit(path, packs_by_label, windows, weights_by_label, focus_legs):
    fields = ["label", "days", "date", "total"] + focus_legs + ["other_total"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for label, weights in weights_by_label.items():
            for days in windows:
                pack = packs_by_label[label][days]
                vals, parts = _combined_daily(pack, weights)
                if len(vals) == 0:
                    continue
                idx = int(vals.argmin())
                zeros = np.zeros(len(vals))
                leg_vals = {leg: float(parts.get(leg, zeros)[idx]) for leg in focus_legs}
                row = {
                    "label": label,
                    "days": days,
                    "date": pack["days"][idx],
                    "total": round(float(vals[idx]), 4),
                    "other_total": round(float(vals[idx] - sum(leg_vals.values())), 4),
                }
                row.update({leg: round(v, 4) for leg, v in leg_vals.items()})
                w.writerow(row)


def _write_daily_audit(path, packs, windows, label, weights, focus_legs):
    fields = ["label", "days", "date", "total"] + focus_legs + ["other_total"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for days in windows:
            pack = packs[days]
            vals, parts = _combined_daily(pack, weights)
            zeros = np.zeros(len(vals))
            for idx, date in enumerate(pack["days"]):
                leg_vals = {leg: float(parts.get(leg, zeros)[idx]) for leg in focus_legs}
                row = {
                    "label": label,
                    "days": days,
                    "date": date,
                    "total": round(float(vals[idx]), 4),
                    "other_total": round(float(vals[idx] - sum(leg_vals.values())), 4),
                }
                row.update({leg: round(v, 4) for leg, v in leg_vals.items()})
                w.writerow(row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="90,120,150,180")
    ap.add_argument("--cache-dir", default=os.path.join(ROOT_DIR, "tmp", "s72_cache"))
    ap.add_argument("--preset", choices=["micro", "tiny"], default="micro")
    ap.add_argument("--w", default="0:20:0.25")
    ap.add_argument("--floor", type=float, default=-1000.0)
    ap.add_argument("--floors", default="-700,-900,-973.16,-999.91,-1000")
    ap.add_argument("--max-streak", type=int, default=3)
    ap.add_argument("--max-configs", type=int, default=0)
    ap.add_argument("--out", default="s87_siglevel_overlay_search.csv")
    ap.add_argument("--audit-out", default="s87_siglevel_overlay_worst_day.csv")
    ap.add_argument("--daily-out", default="")
    ap.add_argument("--top", type=int, default=250)
    args = ap.parse_args()

    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    w_grid = _frange(args.w)
    floors = [float(x.strip()) for x in args.floors.split(",") if x.strip()]

    configs = [_make_cfg(vals) for vals in itertools.product(*_grid(args.preset))]
    if args.max_configs > 0:
        configs = configs[:args.max_configs]
    tfs = sorted({cfg["ENTRY_TF"] for cfg in configs})

    if not config.mt5_initialize(mt5):
        raise SystemExit(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
    try:
        base_packs = _build_s86_packs(windows, args.cache_dir, ["M30"])
        bars_by_tf_days = {
            (tf, days): _fetch_tf_bars(tf, days)
            for tf in tfs
            for days in windows
        }
    finally:
        mt5.shutdown()

    base_weights = _base_weights()
    base_rows = [_window_stats(base_packs[d], base_weights, d) for d in windows]
    base_summary = _summary(base_rows)

    candidates = []
    for cfg_idx, cfg in enumerate(configs, 1):
        label = _cfg_label(cfg)
        cfg_packs = {}
        raw_counts = {}
        for days in windows:
            bars = bars_by_tf_days[(cfg["ENTRY_TF"], days)]
            run_cfg = dict(cfg)
            run_cfg["_ATR14"] = _atr_series(bars, 14)
            run_cfg["_DT_BKK"] = [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]
            raw = run_siglevel(bars, run_cfg, days, DEFAULT_SPREAD)
            twp, eq, by_day = _simulate_leg(raw, SIGLEVEL_CFG)
            raw_counts[days] = len(raw)
            cfg_packs[days] = _pack_with_siglevel(base_packs[days], label, twp, eq, by_day)
        for weight in w_grid:
            weights = dict(base_weights)
            weights[label] = weight
            rows = [_window_stats(cfg_packs[d], weights, d) for d in windows]
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
            candidates.append((score, label, cfg, weight, rows, summary, beats, cfg_packs, raw_counts))
    candidates.sort(key=lambda x: x[0], reverse=True)

    fields = [
        "timestamp", "rank", "label", "add_weight", "beats_s86",
        "floor_flags", "score", "avg_day", "min_day", "min_pf", "max_streak",
        "worst_day", "max_lot", "max_leg_dd_pct", "skipped_by_cb", "days",
        "day", "daily_pf", "window_streak", "window_worst_day", "best_day",
        "trade_units", "by_leg", "raw_counts",
    ]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in base_rows:
            row = _row(ts, 0, "S86_BASELINE", "", "", "", _floor_flags(base_summary, floors), base_summary, r)
            row["raw_counts"] = ""
            w.writerow(row)
        for rank, (score, label, _cfg, weight, rows, summary, beats, _packs, raw_counts) in enumerate(candidates[:args.top], 1):
            flags = _floor_flags(summary, floors)
            rc = ";".join(f"{k}d:{v}" for k, v in sorted(raw_counts.items()))
            for r in rows:
                row = _row(ts, rank, label, weight, score, beats, flags, summary, r)
                row["raw_counts"] = rc
                w.writerow(row)

    audit_packs = {"S86_BASELINE": base_packs}
    audit_weights = {"S86_BASELINE": dict(base_weights)}
    for _score, label, _cfg, weight, _rows, _cand_summary, _beats, packs, _raw_counts in candidates[:20]:
        weights = dict(base_weights)
        weights[label] = weight
        audit_packs[f"{label}x{weight:g}"] = packs
        audit_weights[f"{label}x{weight:g}"] = weights
    top_focus = ["S208_M1", "S2010_M30_FSP"]
    if candidates:
        top_focus.append(candidates[0][1])
    _write_worst_day_audit(args.audit_out, audit_packs, windows, audit_weights, top_focus)
    if args.daily_out and candidates:
        _score, label, _cfg, weight, _rows, _cand_summary, _beats, packs, _raw_counts = candidates[0]
        weights = dict(base_weights)
        weights[label] = weight
        _write_daily_audit(args.daily_out, packs, windows, f"{label}x{weight:g}", weights, top_focus)

    print(
        f"S86_BASELINE avg$/d={base_summary['avg_day']:.2f} min$/d={base_summary['min_day']:.2f} "
        f"PF={base_summary['min_pf']:.2f} st={base_summary['max_streak']} worst={base_summary['worst_day']:.2f}"
    )
    print(f"Significant-level configs={len(configs)} preset={args.preset} tfs={','.join(tfs)}")
    print("Top S87 significant-level candidates:")
    for i, (score, label, _cfg, weight, rows, summary, beats, _packs, raw_counts) in enumerate(candidates[:20], 1):
        print(
            f"{i:>2}. {label}x{weight:g} avg$/d={summary['avg_day']:.2f} "
            f"min$/d={summary['min_day']:.2f} minPF={summary['min_pf']:.2f} "
            f"st={summary['max_streak']} worst={summary['worst_day']:.2f} "
            f"beats={beats} floors={_floor_flags(summary, floors)} raw={raw_counts}"
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
