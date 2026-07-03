"""
optimize_s85_significant_level.py - Search S85 Significant Level Rejection configs.

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
from sim_s64_backtest import _fixed_lot_stats
from sim_s85_backtest import DEFAULT_SPREAD, START_EQUITY, run_single
from strategy85 import S85_DEFAULTS


def _pf_from_daily(by_day):
    gross_win = sum(v for v in by_day.values() if v > 0)
    gross_loss = sum(abs(v) for v in by_day.values() if v <= 0)
    if gross_loss <= 0:
        return 99.0 if gross_win > 0 else 0.0
    return gross_win / gross_loss


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


def _row_exact(raw, cfg, days):
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
        f"{cfg['ENTRY_TF']}_lb{cfg['LOOKBACK']}_age{cfg['MIN_LEVEL_AGE']}"
        f"_t{cfg['TOUCH_TOL_ATR']:g}_a{cfg['CLOSE_AWAY_ATR']:g}"
        f"_w{cfg['MIN_REJECT_WICK_ATR']:g}_wb{cfg['WICK_BODY_MULT']:g}"
        f"_dj{int(cfg['USE_DOJI_LEVELS'])}_pv{int(cfg['USE_PIVOT_LEVELS'])}"
        f"_tr{int(cfg['REQUIRE_TREND_INTO_LEVEL'])}_tl{cfg['TREND_LOOKBACK']}"
        f"_tm{cfg['TREND_MIN_ATR']:g}_sl{cfg['SL_ATR_MULT']:g}_rr{cfg['TP_RR']:g}"
    )


def _grid(preset):
    if preset == "micro":
        return (
            ["M5"],
            [72],
            [8, 12],
            [0.12],
            [0.06],
            [0.24],
            [1.0],
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
            ["M5", "M15"],
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="90,120,150,180")
    ap.add_argument("--out", default="s85_significant_level_optimize.csv")
    ap.add_argument("--preset", choices=["micro", "tiny"], default="micro")
    ap.add_argument("--mode", choices=["exact", "fixed", "scout"], default="scout")
    ap.add_argument("--validate-top", type=int, default=20)
    ap.add_argument("--max-configs", type=int, default=0)
    args = ap.parse_args()
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]

    if not config.mt5_initialize(mt5):
        raise SystemExit(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
    bars_by_tf_days = {}
    for tf in sorted(set(_grid(args.preset)[0])):
        for days in windows:
            bars_by_tf_days[(tf, days)] = s30sim.fetch_bars(config.SYMBOL, tf, days, extra_bars=700)
    mt5.shutdown()

    configs = []
    for vals in itertools.product(*_grid(args.preset)):
        tf, lb, age, touch, away, wick, wickbody, doji, pivot, trend, tlb, tmin, slmult, rr = vals
        cfg = dict(S85_DEFAULTS)
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
            rows.append(_row_exact(raw, cfg, days) if args.mode == "exact" else _row_fixed(raw, days, DEFAULT_SPREAD))
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
                rows.append(_row_exact(raw, cfg, days))
            summary = _summary(rows)
            results.append((_score(summary), cfg, rows, summary))
        results.sort(key=lambda x: x[0], reverse=True)
    else:
        results = fixed_results

    fields = [
        "timestamp", "rank", "mode", "label", "score", "avg_day", "min_day",
        "min_pf", "max_streak", "worst_day", "max_lot", "max_dd", "skipped",
        "min_trades", "days", "trades", "day", "pf", "streak", "window_worst_day",
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

    print("Top S85 configs:")
    for i, (score, cfg, rows, summary) in enumerate(results[:15], 1):
        print(
            f"{i:>2}. {_cfg_label(cfg)} avg$/d={summary['avg_day']:.2f} "
            f"min$/d={summary['min_day']:.2f} minPF={summary['min_pf']:.2f} "
            f"st={summary['max_streak']} worst={summary['worst_day']:.2f} "
            f"tradesMin={summary['trades']} score={score}"
        )
        print("  " + " | ".join(
            f"{r['days']}d {r['trades']}tr {r['day']:.2f}/d PF={r['pf']:.2f} st={r['streak']}"
            for r in rows
        ))
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
