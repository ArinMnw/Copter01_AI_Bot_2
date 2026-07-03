"""
optimize_s87_siglevel_fast.py - Fast S87 Significant Level overlay search above S86.

RESEARCH/BACKTEST-ONLY. No live bot wiring.

This runner uses the already verified S86 daily CSV as the base portfolio and
simulates only the new significant-level leg with the same per-leg sizing:
    simulate_equity_substream(raw, cfg, START_EQUITY=1000)

It is intended as a faster search pass after S86 has already been reproduced
and written to `s86_s2010_m30_fsp_fine_daily.csv`.
"""

import argparse
import csv
import itertools
from datetime import datetime

import MetaTrader5 as mt5
import numpy as np

import config
import sim_s30_backtest as s30sim
from optimize_s72_vs_demo_portfolio import DEFAULT_SPREAD
from optimize_s75_champion_formula import _simulate_leg
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

S86_BASE_MAX_LOT = 0.19
S86_BASE_MAX_DD = 55.01
S86_BASE_SKIPPED = 9839

TF_EXTRA_BARS = {"M5": 1100, "M15": 700, "M30": 520, "H1": 420}


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
    if preset == "small":
        return (
            ["M5", "M15", "M30", "H1"],
            [48, 72, 96],
            [5, 8, 12],
            [0.06, 0.12, 0.20],
            [0.03, 0.08],
            [0.14, 0.24, 0.36],
            [0.6, 1.0],
            [True, False],
            [True],
            [True, False],
            [10, 16],
            [0.6, 1.0, 1.5],
            [0.20, 0.35],
            [0.9, 1.2, 1.6],
        )
    raise ValueError(preset)


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


def _cfg_label(cfg):
    return (
        f"S85SIG_{cfg['ENTRY_TF']}_lb{cfg['LOOKBACK']}_age{cfg['MIN_LEVEL_AGE']}"
        f"_t{cfg['TOUCH_TOL_ATR']:g}_a{cfg['CLOSE_AWAY_ATR']:g}"
        f"_w{cfg['MIN_REJECT_WICK_ATR']:g}_wb{cfg['WICK_BODY_MULT']:g}"
        f"_dj{int(cfg['USE_DOJI_LEVELS'])}_pv{int(cfg['USE_PIVOT_LEVELS'])}"
        f"_tr{int(cfg['REQUIRE_TREND_INTO_LEVEL'])}_tl{cfg['TREND_LOOKBACK']}"
        f"_tm{cfg['TREND_MIN_ATR']:g}_sl{cfg['SL_ATR_MULT']:g}_rr{cfg['TP_RR']:g}"
    )


def _load_base_daily(path, windows):
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            days = int(r["days"])
            if days not in windows:
                continue
            out.setdefault(days, []).append((r["date"], float(r["total"])))
    for days in windows:
        out[days] = sorted(out.get(days, []), key=lambda x: x[0])
        if not out[days]:
            raise SystemExit(f"missing base daily rows for {days}d in {path}")
    return out


def _pf(vals):
    vals = np.asarray(vals, dtype=float)
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


def _base_rows(base_daily, windows):
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
            "max_lot": S86_BASE_MAX_LOT,
            "max_dd": S86_BASE_MAX_DD,
            "skipped": S86_BASE_SKIPPED,
        })
    return rows


def _floor_flags(summary, floors):
    return ";".join(
        f"{floor:g}:{'PASS' if summary['worst_day'] >= floor else 'FAIL'}"
        for floor in floors
    )


def _fetch_tf_bars(tf_name, days):
    return s30sim.fetch_bars(config.SYMBOL, tf_name, days, extra_bars=TF_EXTRA_BARS.get(tf_name, 700))


def _invert_raw(raw):
    out = []
    for t in raw:
        x = dict(t)
        sig = str(x.get("signal", ""))
        x["signal"] = "SELL" if sig == "BUY" else "BUY" if sig == "SELL" else sig
        x["tp"], x["sl"] = x["sl"], x["tp"]
        x["outcome"] = "TP" if x.get("outcome") == "SL" else "SL" if x.get("outcome") == "TP" else x.get("outcome")
        x["diff_usd_per_001lot"] = round(-float(x.get("diff_usd_per_001lot", 0.0)), 4)
        x["reason"] = f"inverse_siglevel | {x.get('reason', '')}"
        out.append(x)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="90,120,150,180")
    ap.add_argument("--base-daily", default="s86_s2010_m30_fsp_fine_daily.csv")
    ap.add_argument("--preset", choices=["micro", "small"], default="micro")
    ap.add_argument("--max-configs", type=int, default=0)
    ap.add_argument("--skip-configs", type=int, default=0)
    ap.add_argument("--w", default="0:20:0.5")
    ap.add_argument("--invert", action="store_true")
    ap.add_argument("--floor", type=float, default=-1000.0)
    ap.add_argument("--floors", default="-700,-900,-973.16,-999.91,-1000")
    ap.add_argument("--max-streak", type=int, default=3)
    ap.add_argument("--out", default="s87_siglevel_fast.csv")
    ap.add_argument("--audit-out", default="s87_siglevel_fast_worst_day.csv")
    ap.add_argument("--top", type=int, default=220)
    args = ap.parse_args()

    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    floors = [float(x.strip()) for x in args.floors.split(",") if x.strip()]
    w_grid = _frange(args.w)

    configs = [_make_cfg(vals) for vals in itertools.product(*_grid(args.preset))]
    if args.skip_configs:
        configs = configs[args.skip_configs:]
    if args.max_configs > 0:
        configs = configs[:args.max_configs]
    tfs = sorted({cfg["ENTRY_TF"] for cfg in configs})
    base_daily = _load_base_daily(args.base_daily, windows)
    base_summary = _summ(_base_rows(base_daily, windows))

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

    candidates = []
    for cfg in configs:
        label = _cfg_label(cfg)
        leg_arrays = {}
        eq_by_days = {}
        raw_counts = {}
        for days in windows:
            bars = bars_by_tf_days[(cfg["ENTRY_TF"], days)]
            run_cfg = dict(cfg)
            run_cfg["_ATR14"] = _atr_series(bars, 14)
            run_cfg["_DT_BKK"] = [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]
            raw = run_siglevel(bars, run_cfg, days, DEFAULT_SPREAD)
            if args.invert:
                raw = _invert_raw(raw)
            twp, eq, by_day = _simulate_leg(raw, SIGLEVEL_CFG)
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
                    "max_lot": max(S86_BASE_MAX_LOT, float(eq.get("lot_max", 0.0))),
                    "max_dd": max(S86_BASE_MAX_DD, float(eq.get("max_dd_pct", 0.0))),
                    "skipped": S86_BASE_SKIPPED + int(eq.get("skipped_by_circuit_breaker", 0)),
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
        "timestamp", "rank", "label", "add_weight", "beats_s86", "floor_flags",
        "score", "avg_day", "min_day", "min_pf", "max_streak", "worst_day",
        "max_lot", "max_leg_dd_pct", "skipped_by_cb", "days", "day",
        "daily_pf", "window_streak", "window_worst_day", "best_day", "raw_counts",
    ]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in _base_rows(base_daily, windows):
            w.writerow({
                "timestamp": ts, "rank": 0, "label": "S86_BASELINE", "add_weight": "",
                "beats_s86": "", "floor_flags": _floor_flags(base_summary, floors), "score": "",
                "avg_day": round(base_summary["avg_day"], 2), "min_day": round(base_summary["min_day"], 2),
                "min_pf": round(base_summary["min_pf"], 3), "max_streak": base_summary["max_streak"],
                "worst_day": round(base_summary["worst_day"], 2), "max_lot": S86_BASE_MAX_LOT,
                "max_leg_dd_pct": S86_BASE_MAX_DD, "skipped_by_cb": S86_BASE_SKIPPED,
                "days": r["days"], "day": round(r["day"], 2), "daily_pf": round(r["pf"], 3),
                "window_streak": r["streak"], "window_worst_day": round(r["worst_day"], 2),
                "best_day": round(r["best_day"], 2), "raw_counts": "",
            })
        for rank, (score, label, weight, rows, summary, beats, raw_counts, _leg_arrays) in enumerate(candidates[:args.top], 1):
            rc = ";".join(f"{k}d:{v}" for k, v in sorted(raw_counts.items()))
            for r in rows:
                w.writerow({
                    "timestamp": ts, "rank": rank, "label": label, "add_weight": weight,
                    "beats_s86": beats, "floor_flags": _floor_flags(summary, floors), "score": score,
                    "avg_day": round(summary["avg_day"], 2), "min_day": round(summary["min_day"], 2),
                    "min_pf": round(summary["min_pf"], 3), "max_streak": summary["max_streak"],
                    "worst_day": round(summary["worst_day"], 2), "max_lot": round(summary["max_lot"], 2),
                    "max_leg_dd_pct": round(summary["max_dd"], 2), "skipped_by_cb": summary["skipped"],
                    "days": r["days"], "day": round(r["day"], 2), "daily_pf": round(r["pf"], 3),
                    "window_streak": r["streak"], "window_worst_day": round(r["worst_day"], 2),
                    "best_day": round(r["best_day"], 2), "raw_counts": rc,
                })

    with open(args.audit_out, "w", newline="", encoding="utf-8") as f:
        fields_a = ["label", "days", "date", "total", "base", "siglevel", "weight"]
        w = csv.DictWriter(f, fieldnames=fields_a)
        w.writeheader()
        for label, weight, leg_arrays in [("S86_BASELINE", 0.0, None)] + [
            (f"{label}x{weight:g}", weight, leg_arrays)
            for _score, label, weight, _rows, _summary, _beats, _raw_counts, leg_arrays in candidates[:20]
        ]:
            for days in windows:
                dates = [d for d, _v in base_daily[days]]
                base_vals = np.array([v for _d, v in base_daily[days]], dtype=float)
                sig_vals = np.zeros(len(base_vals)) if leg_arrays is None else leg_arrays[days] * weight
                vals = base_vals + sig_vals
                idx = int(vals.argmin())
                w.writerow({
                    "label": label, "days": days, "date": dates[idx],
                    "total": round(float(vals[idx]), 4), "base": round(float(base_vals[idx]), 4),
                    "siglevel": round(float(sig_vals[idx]), 4), "weight": weight,
                })

    print(
        f"S86_BASELINE avg$/d={base_summary['avg_day']:.2f} min$/d={base_summary['min_day']:.2f} "
        f"PF={base_summary['min_pf']:.2f} st={base_summary['max_streak']} worst={base_summary['worst_day']:.2f}"
    )
    print(f"Significant-level fast configs={len(configs)} preset={args.preset} tfs={','.join(tfs)}")
    if args.invert:
        print("Mode: inverse significant-level raw")
    print("Top S87 significant-level fast candidates:")
    for i, (score, label, weight, rows, summary, beats, raw_counts, _leg_arrays) in enumerate(candidates[:20], 1):
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


if __name__ == "__main__":
    main()
