"""
optimize_s65_fake_trap.py - Search S65 Fake Reversal Trap configs.

RESEARCH/BACKTEST-ONLY. No live bot wiring.
"""

import argparse
import csv
import itertools
from datetime import datetime

import MetaTrader5 as mt5

import config
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim
from sim_s62_backtest import _atr_series
from sim_s65_backtest import DEFAULT_SPREAD, START_EQUITY, run_single
from sim_s64_backtest import _fixed_lot_stats
from strategy65 import S65_DEFAULTS


def _summary(rows):
    return {
        "avg_day": sum(r["day"] for r in rows) / len(rows),
        "min_day": min(r["day"] for r in rows),
        "min_pf": min(r["pf"] for r in rows),
        "max_streak": max(r["streak"] for r in rows),
        "worst_day": min(r["worst_day"] for r in rows),
        "max_lot": max(r["max_lot"] for r in rows),
        "max_dd": max(r["max_dd"] for r in rows),
        "skipped": max(r["skipped"] for r in rows),
        "trades": min(r["trades"] for r in rows),
    }


def _pf_from_daily(by_day):
    gross_win = sum(v for v in by_day.values() if v > 0)
    gross_loss = sum(abs(v) for v in by_day.values() if v <= 0)
    if gross_loss <= 0:
        return 99.0 if gross_win > 0 else 0.0
    return gross_win / gross_loss


def _row(raw, cfg, days):
    twp, eq = s31sim.simulate_equity_substream(raw, cfg, START_EQUITY)
    by_day = s31sim.daily_series_from_trades(twp)
    c = s31sim.consistency_metrics(by_day) or {"max_losing_day_streak": 0}
    vals = list(by_day.values())
    return {
        "days": days,
        "trades": len(twp),
        "day": sum(vals) / days if days else 0.0,
        "pf": _pf_from_daily(by_day),
        "streak": c["max_losing_day_streak"],
        "worst_day": min(vals) if vals else 0.0,
        "max_lot": float(eq.get("lot_max", 0.0)),
        "max_dd": float(eq.get("max_dd_pct", 0.0)),
        "skipped": int(eq.get("skipped_by_circuit_breaker", 0)),
    }


def _row_fixed(raw, days, spread):
    fs = _fixed_lot_stats(raw, days, spread)
    by_day = {}
    for t in raw:
        pnl = float(t["diff_usd_per_001lot"]) - spread
        d = config.mt5_ts_to_bkk(t["exit_time_ts"]).strftime("%Y-%m-%d")
        by_day[d] = by_day.get(d, 0.0) + pnl
    vals = list(by_day.values())
    return {
        "days": days,
        "trades": fs["trades"],
        "day": fs["fixed_per_day"],
        "pf": fs["fixed_pf"],
        "streak": fs["max_losing_day_streak"],
        "worst_day": min(vals) if vals else 0.0,
        "max_lot": 0.0,
        "max_dd": 0.0,
        "skipped": 0,
    }


def _score(summary):
    return (
        1 if summary["max_streak"] <= 3 else 0,
        1 if summary["worst_day"] >= -1000 else 0,
        round(summary["avg_day"], 6),
        round(summary["min_day"], 6),
        round(summary["min_pf"], 6),
        -summary["max_streak"],
        round(summary["worst_day"], 4),
    )


def _cfg_label(cfg):
    return (
        f"{cfg['ENTRY_TF']}_lb{cfg['LEG_LOOKBACK']}_pb{cfg['PULLBACK_BARS']}"
        f"_lm{cfg['LEG_MIN_ATR']:g}_pm{cfg['PULLBACK_MIN_ATR']:g}"
        f"_ft{cfg['FAIL_TOL_ATR']:g}_cf{cfg['CONFIRM_BODY_ATR']:g}"
        f"_sl{cfg['SL_ATR_MULT']:g}_rr{cfg['TP_RR']:g}_flip{int(cfg['FLIP_SIGNAL'])}"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="90,120,150,180")
    ap.add_argument("--out", default="s65_fake_trap_optimize.csv")
    ap.add_argument("--preset", choices=["micro", "tiny", "coarse", "full"], default="coarse")
    ap.add_argument("--mode", choices=["exact", "fixed", "scout"], default="exact")
    ap.add_argument("--validate-top", type=int, default=40)
    ap.add_argument("--max-configs", type=int, default=0)
    args = ap.parse_args()
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]

    if not config.mt5_initialize(mt5):
        raise SystemExit(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
    bars_by_tf_days = {}
    for tf in ["M5", "M15"]:
        for days in windows:
            bars_by_tf_days[(tf, days)] = s30sim.fetch_bars(config.SYMBOL, tf, days, extra_bars=620)
    mt5.shutdown()

    configs = []
    if args.preset == "micro":
        grid = (
            ["M5"],
            [10, 18],
            [3, 4],
            [0.7, 1.3],
            [0.15],
            [0.05],
            [0.10],
            [0.25, 0.45],
            [1.0, 1.5],
            [False, True],
        )
    elif args.preset == "tiny":
        grid = (
            ["M5"],
            [10, 18],
            [3, 4],
            [0.7, 1.3],
            [0.15, 0.35],
            [0.05],
            [0.10, 0.22],
            [0.25, 0.45],
            [1.0, 1.5],
            [False, True],
        )
    elif args.preset == "coarse":
        grid = (
            ["M5", "M15"],
            [10, 18, 24],
            [3, 4],
            [0.7, 1.3],
            [0.15, 0.35],
            [0.05, 0.20],
            [0.10, 0.22],
            [0.25, 0.45],
            [1.0, 1.5],
            [False, True],
        )
    else:
        grid = (
            ["M5", "M15"],
            [10, 14, 18, 24],
            [2, 3, 4, 5],
            [0.7, 1.0, 1.3, 1.7],
            [0.15, 0.25, 0.35, 0.50],
            [0.05, 0.15, 0.30],
            [0.10, 0.18, 0.28],
            [0.25, 0.35, 0.50],
            [1.0, 1.25, 1.5, 2.0],
            [False, True],
        )

    for tf, lb, pb, legmin, pullmin, failtol, confirm, slmult, rr, flip in itertools.product(*grid):
        cfg = dict(S65_DEFAULTS)
        cfg.update({
            "ENTRY_TF": tf,
            "LEG_LOOKBACK": lb,
            "PULLBACK_BARS": pb,
            "LEG_MIN_ATR": legmin,
            "PULLBACK_MIN_ATR": pullmin,
            "FAIL_TOL_ATR": failtol,
            "CONFIRM_BODY_ATR": confirm,
            "SL_ATR_MULT": slmult,
            "TP_RR": rr,
            "FLIP_SIGNAL": flip,
        })
        configs.append(cfg)
    if args.max_configs > 0:
        configs = configs[:args.max_configs]

    fixed_results = []
    for cfg in configs:
        rows = []
        for days in windows:
            bars = bars_by_tf_days[(cfg["ENTRY_TF"], days)]
            run_cfg = dict(cfg)
            run_cfg["_ATR14"] = _atr_series(bars, 14)
            run_cfg["_DT_BKK"] = [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]
            raw = run_single(bars, run_cfg, days, DEFAULT_SPREAD)
            if args.mode == "exact":
                rows.append(_row(raw, cfg, days))
            else:
                rows.append(_row_fixed(raw, days, DEFAULT_SPREAD))
        summary = _summary(rows)
        fixed_results.append((_score(summary), cfg, rows, summary))
    fixed_results.sort(key=lambda x: x[0], reverse=True)

    if args.mode == "scout":
        results = []
        for _, cfg, _, _ in fixed_results[:max(1, args.validate_top)]:
            rows = []
            for days in windows:
                bars = bars_by_tf_days[(cfg["ENTRY_TF"], days)]
                run_cfg = dict(cfg)
                run_cfg["_ATR14"] = _atr_series(bars, 14)
                run_cfg["_DT_BKK"] = [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]
                raw = run_single(bars, run_cfg, days, DEFAULT_SPREAD)
                rows.append(_row(raw, cfg, days))
            summary = _summary(rows)
            results.append((_score(summary), cfg, rows, summary))
        results.sort(key=lambda x: x[0], reverse=True)
    else:
        results = fixed_results

    fields = [
        "timestamp", "rank", "mode", "label", "score", "avg_day", "min_day", "min_pf",
        "max_streak", "worst_day", "max_lot", "max_dd", "skipped", "min_trades",
        "days", "trades", "day", "pf", "streak", "window_worst_day",
    ]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for rank, (score, cfg, rows, summary) in enumerate(results[:120], 1):
            for r in rows:
                w.writerow({
                    "timestamp": ts,
                    "rank": rank,
                    "mode": args.mode,
                    "label": _cfg_label(cfg),
                    "score": score,
                    "avg_day": round(summary["avg_day"], 2),
                    "min_day": round(summary["min_day"], 2),
                    "min_pf": round(summary["min_pf"], 3),
                    "max_streak": summary["max_streak"],
                    "worst_day": round(summary["worst_day"], 2),
                    "max_lot": round(summary["max_lot"], 2),
                    "max_dd": round(summary["max_dd"], 2),
                    "skipped": summary["skipped"],
                    "min_trades": summary["trades"],
                    "days": r["days"],
                    "trades": r["trades"],
                    "day": round(r["day"], 2),
                    "pf": round(r["pf"], 3),
                    "streak": r["streak"],
                    "window_worst_day": round(r["worst_day"], 2),
                })

    print("Top S65 configs:")
    for i, (score, cfg, rows, summary) in enumerate(results[:15], 1):
        print(
            f"{i:>2}. {_cfg_label(cfg)} avg$/d={summary['avg_day']:.2f} "
            f"min$/d={summary['min_day']:.2f} minPF={summary['min_pf']:.2f} "
            f"st={summary['max_streak']} worst={summary['worst_day']:.2f} tradesMin={summary['trades']} "
            f"score={score}"
        )
        print("  " + " | ".join(
            f"{r['days']}d {r['trades']}tr {r['day']:.2f}/d PF={r['pf']:.2f} st={r['streak']}"
            for r in rows
        ))
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
