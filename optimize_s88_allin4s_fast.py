"""
optimize_s88_allin4s_fast.py - Fast S88 All-in-4S overlay search above S87.

RESEARCH/BACKTEST-ONLY. No live bot wiring.

This runner first rebuilds the S87 micro baseline:
    S87 = S86 daily + inverse(S85SIG_M30)x0.007

Then it tests a new All-in-4S overlay family with the same portfolio sizing
framework used by the champion ladder:
    simulate_equity_substream(raw, cfg, START_EQUITY=1000)
per leg, then sums daily PnL by weight.
"""

import argparse
import csv
import itertools
import re
from datetime import datetime

import MetaTrader5 as mt5
import numpy as np

import config
import sim_s30_backtest as s30sim
from optimize_s72_vs_demo_portfolio import DEFAULT_SPREAD
from optimize_s75_champion_formula import _simulate_leg
from optimize_s87_siglevel_fast import (
    SIGLEVEL_CFG,
    _invert_raw,
    _load_base_daily,
    _max_losing_streak,
    _pf,
)
from sim_s62_backtest import _atr_series
from sim_s84_backtest import run_single as run_s84
from sim_s85_backtest import run_single as run_siglevel
from sim_s86_backtest import run_single as run_s86
from strategy84 import S84_DEFAULTS
from strategy85 import S85_DEFAULTS
from strategy86 import S86_DEFAULTS


S87_MICRO_WEIGHT = 0.007
S87_MAX_LOT = 0.19
S87_MAX_DD = 55.01
S87_SKIPPED = 9909

OVERLAY_CFG = {
    "RISK_PCT": 0.5,
    "DD_CONTROL": "circuit_breaker",
    "CONSEC_LOSS_TRIGGER": 3,
    "REDUCED_RISK_PCT": 0.35,
    "COOLDOWN_TRADES": 10,
}

TF_EXTRA_BARS = {"M5": 1100, "M15": 760, "M30": 560, "H1": 460}

S87_SIG_CFG = dict(S85_DEFAULTS)
S87_SIG_CFG.update(SIGLEVEL_CFG)
S87_SIG_CFG.update({
    "ENTRY_TF": "M30",
    "LOOKBACK": 72,
    "MIN_LEVEL_AGE": 8,
    "TOUCH_TOL_ATR": 0.08,
    "CLOSE_AWAY_ATR": 0.04,
    "MIN_REJECT_WICK_ATR": 0.18,
    "WICK_BODY_MULT": 0.8,
    "USE_DOJI_LEVELS": False,
    "USE_PIVOT_LEVELS": True,
    "REQUIRE_TREND_INTO_LEVEL": True,
    "TREND_LOOKBACK": 12,
    "TREND_MIN_ATR": 0.8,
    "SL_ATR_MULT": 0.25,
    "TP_RR": 1.0,
})


def _frange(spec):
    start, stop, step = [float(x) for x in spec.split(":")]
    vals = []
    cur = start
    while cur <= stop + 1e-9:
        vals.append(round(cur, 4))
        cur += step
    return vals


def _summ(rows):
    return {
        "avg_day": sum(r["day"] for r in rows) / len(rows),
        "min_day": min(r["day"] for r in rows),
        "min_pf": min(r["pf"] for r in rows),
        "max_streak": max(r["streak"] for r in rows),
        "worst_day": min(r["worst_day"] for r in rows),
        "max_lot": max(r["max_lot"] for r in rows),
        "max_dd": max(r["max_dd"] for r in rows),
        "skipped": max(r["skipped"] for r in rows),
    }


def _floor_flags(summary, floors):
    return ";".join(
        f"{floor:g}:{'PASS' if summary['worst_day'] >= floor else 'FAIL'}"
        for floor in floors
    )


def _fetch_tf_bars(tf_name, days):
    return s30sim.fetch_bars(
        config.SYMBOL,
        tf_name,
        days,
        extra_bars=TF_EXTRA_BARS.get(tf_name, 700),
    )


def _cfg_label(family, cfg):
    if family == "s84":
        return (
            f"S84_{cfg['ENTRY_TF']}_lb{cfg['LOOKBACK']}_rw{cfg['REF_MIN_WICK_ATR']:g}"
            f"_wb{cfg['REF_WICK_BODY_MULT']:g}_eat{cfg['EAT_TOL_ATR']:g}"
            f"_fail{cfg['CLOSE_FAIL_ATR']:g}_op{int(cfg['REQUIRE_OPPOSITE_CLOSE'])}"
            f"_mb{cfg['MIN_BODY_ATR']:g}_mr{cfg['MIN_RANGE_ATR']:g}"
            f"_{cfg['TARGET_MODE']}_{cfg['MODE']}_sl{cfg['SL_ATR_MULT']:g}_rr{cfg['TP_RR']:g}"
        )
    return (
        f"S86RUN_{cfg['ENTRY_TF']}_lb{cfg['LOOKBACK']}_imp{cfg['IMPULSE_MIN_ATR']:g}"
        f"_zt{cfg['ZONE_TOL_ATR']:g}_body{cfg['CONFIRM_BODY_ATR']:g}"
        f"_ratio{cfg['CONFIRM_BODY_RATIO']:g}_tr{int(cfg['REQUIRE_TREND'])}"
        f"_tl{cfg['TREND_LOOKBACK']}_tm{cfg['TREND_MIN_ATR']:g}"
        f"_{cfg['SL_MODE']}_{cfg['TP_MODE']}_sl{cfg['SL_ATR_MULT']:g}_rr{cfg['TP_RR']:g}"
    )


def _risk_atr(trade):
    match = re.search(r"riskATR=([0-9.]+)", str(trade.get("reason", "")))
    return float(match.group(1)) if match else 0.0


def _post_filter_raw(raw, args):
    out = []
    for trade in raw:
        if args.risk_atr_max > 0 and _risk_atr(trade) > args.risk_atr_max:
            continue
        if args.risk_distance_min > 0 and float(trade.get("risk_distance", 0.0)) < args.risk_distance_min:
            continue
        if args.risk_distance_max > 0 and float(trade.get("risk_distance", 0.0)) > args.risk_distance_max:
            continue
        if args.fill_hour_from >= 0 or args.fill_hour_before >= 0:
            hour = config.mt5_ts_to_bkk(int(trade["fill_time_ts"])).hour
            if args.fill_hour_from >= 0 and hour < args.fill_hour_from:
                continue
            if args.fill_hour_before >= 0 and hour >= args.fill_hour_before:
                continue
        out.append(trade)
    return out


def _filter_suffix(args):
    parts = []
    if args.risk_atr_max > 0:
        parts.append(f"ratr{args.risk_atr_max:g}")
    if args.risk_distance_min > 0:
        parts.append(f"rdmin{args.risk_distance_min:g}")
    if args.risk_distance_max > 0:
        parts.append(f"rd{args.risk_distance_max:g}")
    if args.fill_hour_from >= 0:
        parts.append(f"hfrom{args.fill_hour_from}")
    if args.fill_hour_before >= 0:
        parts.append(f"hbefore{args.fill_hour_before}")
    return "" if not parts else "_F" + "_".join(parts)


def _grid_s84(preset):
    if preset == "micro":
        return (
            ["M15", "M30"],
            [48, 72],
            [0.25, 0.35],
            [0.8, 1.0],
            [0.06, 0.12],
            [0.03, 0.08],
            [True, False],
            [0.06, 0.12],
            [0.25, 0.35],
            ["mid", "rr"],
            ["revisit", "follow"],
            [0.20, 0.35],
            [0.9, 1.2],
        )
    if preset == "tiny":
        return (
            ["M5", "M15", "M30", "H1"],
            [48, 72, 96],
            [0.25, 0.35, 0.50],
            [0.6, 1.0, 1.4],
            [0.06, 0.12, 0.20],
            [0.03, 0.08, 0.14],
            [True, False],
            [0.06, 0.12],
            [0.25, 0.35, 0.50],
            ["mid", "body", "rr"],
            ["revisit", "follow"],
            [0.20, 0.35, 0.50],
            [0.8, 1.1, 1.5],
        )
    raise ValueError(preset)


def _grid_s86(preset):
    if preset == "micro":
        return (
            ["M15", "M30"],
            [48, 72],
            [1.6, 2.2],
            [0.06, 0.12],
            [0.08, 0.14],
            [0.20, 0.35],
            [True, False],
            [12, 16],
            [0.6, 1.0],
            ["swing", "zone"],
            [0.20, 0.35],
            ["old", "rr"],
            [1.0, 1.3],
        )
    if preset == "tiny":
        return (
            ["M5", "M15", "M30", "H1"],
            [48, 72, 96],
            [1.4, 2.0, 2.8],
            [0.06, 0.12, 0.20],
            [0.08, 0.14, 0.22],
            [0.20, 0.35, 0.50],
            [True, False],
            [10, 16],
            [0.5, 1.0, 1.5],
            ["swing", "zone"],
            [0.20, 0.35, 0.50],
            ["old", "rr"],
            [0.9, 1.2, 1.6],
        )
    raise ValueError(preset)


def _make_s84(vals):
    (
        tf, lb, refwick, wickbody, eattol, fail, opposite, minbody,
        minrange, target, mode, slmult, rr,
    ) = vals
    cfg = dict(S84_DEFAULTS)
    cfg.update(OVERLAY_CFG)
    cfg.update({
        "ENTRY_TF": tf,
        "LOOKBACK": lb,
        "REF_MIN_WICK_ATR": refwick,
        "REF_WICK_BODY_MULT": wickbody,
        "EAT_TOL_ATR": eattol,
        "CLOSE_FAIL_ATR": fail,
        "REQUIRE_OPPOSITE_CLOSE": opposite,
        "MIN_BODY_ATR": minbody,
        "MIN_RANGE_ATR": minrange,
        "TARGET_MODE": target,
        "MODE": mode,
        "SL_ATR_MULT": slmult,
        "TP_RR": rr,
    })
    return cfg


def _make_s86(vals):
    (
        tf, lb, impulse, ztol, body, ratio, trend, tlb, tmin,
        slmode, slmult, tpmode, rr,
    ) = vals
    cfg = dict(S86_DEFAULTS)
    cfg.update(OVERLAY_CFG)
    cfg.update({
        "ENTRY_TF": tf,
        "LOOKBACK": lb,
        "IMPULSE_MIN_ATR": impulse,
        "ZONE_TOL_ATR": ztol,
        "CONFIRM_BODY_ATR": body,
        "CONFIRM_BODY_RATIO": ratio,
        "REQUIRE_TREND": trend,
        "TREND_LOOKBACK": tlb,
        "TREND_MIN_ATR": tmin,
        "SL_MODE": slmode,
        "SL_ATR_MULT": slmult,
        "TP_MODE": tpmode,
        "TP_RR": rr,
    })
    return cfg


def _build_s87_daily(base_s86_daily, windows, bars_by_tf_days):
    out = {}
    for days in windows:
        rows = base_s86_daily[days]
        dates = [d for d, _v in rows]
        base_vals = np.array([v for _d, v in rows], dtype=float)
        bars = bars_by_tf_days[("M30", days)]
        cfg = dict(S87_SIG_CFG)
        cfg["_ATR14"] = _atr_series(bars, 14)
        cfg["_DT_BKK"] = [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]
        raw = _invert_raw(run_siglevel(bars, cfg, days, DEFAULT_SPREAD))
        _twp, _eq, by_day = _simulate_leg(raw, SIGLEVEL_CFG)
        leg_vals = np.array([float(by_day.get(d, 0.0)) for d in dates], dtype=float)
        vals = base_vals + leg_vals * S87_MICRO_WEIGHT
        out[days] = list(zip(dates, vals.tolist()))
    return out


def _daily_rows(base_daily, windows):
    rows = []
    for days in windows:
        vals = np.array([v for _d, v in base_daily[days]], dtype=float)
        rows.append({
            "days": days,
            "day": float(vals.sum()) / days,
            "pf": _pf(vals),
            "streak": _max_losing_streak(vals),
            "worst_day": float(vals.min()),
            "best_day": float(vals.max()),
            "max_lot": S87_MAX_LOT,
            "max_dd": S87_MAX_DD,
            "skipped": S87_SKIPPED,
        })
    return rows


def _write_s87_daily(path, base_daily, windows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["days", "date", "total"])
        w.writeheader()
        for days in windows:
            for date, val in base_daily[days]:
                w.writerow({"days": days, "date": date, "total": round(float(val), 6)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="90,120,150,180")
    ap.add_argument("--base-s86-daily", default="s86_s2010_m30_fsp_fine_daily.csv")
    ap.add_argument("--base-daily", default="",
                    help="optional ready-made base daily CSV with days/date/total columns")
    ap.add_argument("--base-label", default="S87_BASELINE")
    ap.add_argument("--base-skipped", type=int, default=S87_SKIPPED)
    ap.add_argument("--family", choices=["s84", "s86"], default="s84")
    ap.add_argument("--preset", choices=["micro", "tiny"], default="micro")
    ap.add_argument("--mode", choices=["direct", "inverse", "both"], default="both")
    ap.add_argument("--risk-atr-max", type=float, default=0.0)
    ap.add_argument("--risk-distance-min", type=float, default=0.0)
    ap.add_argument("--risk-distance-max", type=float, default=0.0)
    ap.add_argument("--fill-hour-from", type=int, default=-1)
    ap.add_argument("--fill-hour-before", type=int, default=-1)
    ap.add_argument("--max-configs", type=int, default=0)
    ap.add_argument("--skip-configs", type=int, default=0)
    ap.add_argument("--w", default="0:20:0.25")
    ap.add_argument("--floor", type=float, default=-1000.0)
    ap.add_argument("--floors", default="-700,-900,-973.16,-999.91,-1000")
    ap.add_argument("--max-streak", type=int, default=3)
    ap.add_argument("--out", default="s88_allin4s_fast.csv")
    ap.add_argument("--audit-out", default="s88_allin4s_fast_worst_day.csv")
    ap.add_argument("--s87-daily-out", default="s87_micro_daily.csv")
    ap.add_argument("--top", type=int, default=220)
    args = ap.parse_args()

    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    floors = [float(x.strip()) for x in args.floors.split(",") if x.strip()]
    w_grid = _frange(args.w)

    maker = _make_s84 if args.family == "s84" else _make_s86
    grid = _grid_s84(args.preset) if args.family == "s84" else _grid_s86(args.preset)
    runner = run_s84 if args.family == "s84" else run_s86
    configs = [maker(vals) for vals in itertools.product(*grid)]
    if args.skip_configs:
        configs = configs[args.skip_configs:]
    if args.max_configs > 0:
        configs = configs[:args.max_configs]

    tfs = sorted({cfg["ENTRY_TF"] for cfg in configs} | {"M30"})
    if not config.mt5_initialize(mt5):
        raise SystemExit(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
    try:
        bars_by_tf_days = {
            (tf, days): _fetch_tf_bars(tf, days)
            for tf in tfs
            for days in windows
        }
    finally:
        mt5.shutdown()

    if args.base_daily:
        base_daily = _load_base_daily(args.base_daily, windows)
    else:
        base_s86_daily = _load_base_daily(args.base_s86_daily, windows)
        base_daily = _build_s87_daily(base_s86_daily, windows, bars_by_tf_days)
        _write_s87_daily(args.s87_daily_out, base_daily, windows)
    base_rows = _daily_rows(base_daily, windows)
    for row in base_rows:
        row["skipped"] = args.base_skipped
    base_summary = _summ(base_rows)

    modes = ["direct", "inverse"] if args.mode == "both" else [args.mode]
    candidates = []
    for cfg in configs:
        base_label = _cfg_label(args.family, cfg)
        base_label = f"{base_label}{_filter_suffix(args)}"
        for mode in modes:
            label = base_label if mode == "direct" else f"INV_{base_label}"
            leg_arrays = {}
            eq_by_days = {}
            raw_counts = {}
            for days in windows:
                bars = bars_by_tf_days[(cfg["ENTRY_TF"], days)]
                run_cfg = dict(cfg)
                run_cfg["_ATR14"] = _atr_series(bars, 14)
                run_cfg["_DT_BKK"] = [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]
                raw = runner(bars, run_cfg, days, DEFAULT_SPREAD)
                raw = _post_filter_raw(raw, args)
                if mode == "inverse":
                    raw = _invert_raw(raw)
                _twp, eq, by_day = _simulate_leg(raw, OVERLAY_CFG)
                dates = [d for d, _v in base_daily[days]]
                leg_arrays[days] = np.array([float(by_day.get(d, 0.0)) for d in dates], dtype=float)
                eq_by_days[days] = eq
                raw_counts[days] = len(raw)
            for weight in w_grid:
                rows = []
                for days in windows:
                    base_vals = np.array([v for _d, v in base_daily[days]], dtype=float)
                    vals = base_vals + leg_arrays[days] * weight
                    eq = eq_by_days[days]
                    rows.append({
                        "days": days,
                        "day": float(vals.sum()) / days,
                        "pf": _pf(vals),
                        "streak": _max_losing_streak(vals),
                        "worst_day": float(vals.min()),
                        "best_day": float(vals.max()),
                        "max_lot": max(S87_MAX_LOT, float(eq.get("lot_max", 0.0))),
                        "max_dd": max(S87_MAX_DD, float(eq.get("max_dd_pct", 0.0))),
                "skipped": args.base_skipped + int(eq.get("skipped_by_circuit_breaker", 0)),
                    })
                summary = _summ(rows)
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
                candidates.append((score, label, weight, rows, summary, beats, raw_counts, leg_arrays))
    candidates.sort(key=lambda x: x[0], reverse=True)

    fields = [
        "timestamp", "rank", "label", "add_weight", "beats_s87", "floor_flags",
        "score", "avg_day", "min_day", "min_pf", "max_streak", "worst_day",
        "max_lot", "max_leg_dd_pct", "skipped_by_cb", "days", "day",
        "daily_pf", "window_streak", "window_worst_day", "best_day", "raw_counts",
    ]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in base_rows:
            w.writerow({
                "timestamp": ts, "rank": 0, "label": args.base_label, "add_weight": "",
                "beats_s87": "", "floor_flags": _floor_flags(base_summary, floors), "score": "",
                "avg_day": round(base_summary["avg_day"], 2), "min_day": round(base_summary["min_day"], 2),
                "min_pf": round(base_summary["min_pf"], 3), "max_streak": base_summary["max_streak"],
                "worst_day": round(base_summary["worst_day"], 2), "max_lot": S87_MAX_LOT,
                "max_leg_dd_pct": S87_MAX_DD, "skipped_by_cb": args.base_skipped,
                "days": r["days"], "day": round(r["day"], 2), "daily_pf": round(r["pf"], 3),
                "window_streak": r["streak"], "window_worst_day": round(r["worst_day"], 2),
                "best_day": round(r["best_day"], 2), "raw_counts": "",
            })
        for rank, (score, label, weight, rows, summary, beats, raw_counts, _leg_arrays) in enumerate(candidates[:args.top], 1):
            rc = ";".join(f"{k}d:{v}" for k, v in sorted(raw_counts.items()))
            for r in rows:
                w.writerow({
                    "timestamp": ts, "rank": rank, "label": label, "add_weight": weight,
                    "beats_s87": beats, "floor_flags": _floor_flags(summary, floors), "score": score,
                    "avg_day": round(summary["avg_day"], 2), "min_day": round(summary["min_day"], 2),
                    "min_pf": round(summary["min_pf"], 3), "max_streak": summary["max_streak"],
                    "worst_day": round(summary["worst_day"], 2), "max_lot": round(summary["max_lot"], 2),
                    "max_leg_dd_pct": round(summary["max_dd"], 2), "skipped_by_cb": summary["skipped"],
                    "days": r["days"], "day": round(r["day"], 2), "daily_pf": round(r["pf"], 3),
                    "window_streak": r["streak"], "window_worst_day": round(r["worst_day"], 2),
                    "best_day": round(r["best_day"], 2), "raw_counts": rc,
                })

    with open(args.audit_out, "w", newline="", encoding="utf-8") as f:
        fields_a = ["label", "days", "date", "total", "base_s87", "overlay", "weight"]
        w = csv.DictWriter(f, fieldnames=fields_a)
        w.writeheader()
        for label, weight, leg_arrays in [(args.base_label, 0.0, None)] + [
            (f"{label}x{weight:g}", weight, leg_arrays)
            for _score, label, weight, _rows, _summary, _beats, _raw_counts, leg_arrays in candidates[:20]
        ]:
            for days in windows:
                dates = [d for d, _v in base_daily[days]]
                base_vals = np.array([v for _d, v in base_daily[days]], dtype=float)
                overlay_vals = np.zeros(len(base_vals)) if leg_arrays is None else leg_arrays[days] * weight
                vals = base_vals + overlay_vals
                idx = int(vals.argmin())
                w.writerow({
                    "label": label, "days": days, "date": dates[idx],
                    "total": round(float(vals[idx]), 4), "base_s87": round(float(base_vals[idx]), 4),
                    "overlay": round(float(overlay_vals[idx]), 4), "weight": weight,
                })

    print(
        f"{args.base_label} avg$/d={base_summary['avg_day']:.2f} min$/d={base_summary['min_day']:.2f} "
        f"PF={base_summary['min_pf']:.2f} st={base_summary['max_streak']} worst={base_summary['worst_day']:.2f}"
    )
    print(f"S88 family={args.family} configs={len(configs)} preset={args.preset} modes={','.join(modes)}")
    print("Top S88 candidates:")
    for i, (_score, label, weight, rows, summary, beats, raw_counts, _leg_arrays) in enumerate(candidates[:20], 1):
        print(
            f"{i:>2}. {label}x{weight:g} avg$/d={summary['avg_day']:.2f} min$/d={summary['min_day']:.2f} "
            f"minPF={summary['min_pf']:.2f} st={summary['max_streak']} worst={summary['worst_day']:.2f} "
            f"beats={beats} floors={_floor_flags(summary, floors)} raw={raw_counts}"
        )
        print("  " + " | ".join(
            f"{r['days']}d {r['day']:.2f}/d PF={r['pf']:.2f} st={r['streak']} worst={r['worst_day']:.2f}"
            for r in rows
        ))
    print(f"\n-> {args.out}")
    print(f"-> {args.audit_out}")
    print(f"-> {args.s87_daily_out}")


if __name__ == "__main__":
    main()
