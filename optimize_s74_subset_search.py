"""
optimize_s74_subset_search.py - Subset portfolio search toward a safer $1000/day target.

RESEARCH/BACKTEST-ONLY. No live bot wiring.

Uses S72 cache. Search idea:
1. Treat P16 legs as selectable independent legs.
2. Keep the best demo-leg subsets.
3. Add All-in-4S overlays (S63/S69/S64).
4. Rank by the scale needed to make every tested window >= $1000/day, while
   penalizing large worst-day losses and weak PF/streak.
"""

import argparse
import csv
import itertools
import os
from datetime import datetime

import config
import sim_s31_backtest as s31sim

from optimize_s72_vs_demo_portfolio import DEFAULT_SPREAD, ROOT_DIR, _aggregate_raw, _load_cache


DEMO_KEYS = list("ABCDEFGHIKLMNPQR")
ALLIN_KEYS = ["S63", "S69", "S64"]


def _normalize_leg(leg):
    if leg.startswith("P16-"):
        return leg.split("-", 1)[1]
    return leg


def _aggregate_normalized(raw, spread):
    out = {}
    for t in raw:
        x = dict(t)
        x["leg"] = _normalize_leg(str(x.get("leg", "?")))
        leg = x["leg"]
        pnl = float(x["diff_usd_per_001lot"]) - spread
        d = config.mt5_ts_to_bkk(x["exit_time_ts"]).strftime("%Y-%m-%d")
        row = out.setdefault(leg, {
            "trades": 0,
            "gross_win": 0.0,
            "gross_loss": 0.0,
            "total": 0.0,
            "by_day": {},
        })
        row["trades"] += 1
        row["total"] += pnl
        if pnl > 0:
            row["gross_win"] += pnl
        else:
            row["gross_loss"] += abs(pnl)
        row["by_day"][d] = row["by_day"].get(d, 0.0) + pnl
    return out


def _stats(agg, days, weights):
    total = gross_win = gross_loss = 0.0
    units = 0.0
    trades = 0
    by_day = {}
    by_leg = {}
    for leg, w in weights.items():
        if w <= 0 or leg not in agg:
            continue
        row = agg[leg]
        total += row["total"] * w
        gross_win += row["gross_win"] * w
        gross_loss += row["gross_loss"] * w
        trades += row["trades"]
        units += row["trades"] * w
        by_leg[leg] = row["total"] * w
        for d, pnl in row["by_day"].items():
            by_day[d] = by_day.get(d, 0.0) + pnl * w
    c = s31sim.consistency_metrics(by_day) or {
        "pct_pos_days": 0.0,
        "max_losing_day_streak": 0,
        "sharpe_like": 0.0,
    }
    vals = list(by_day.values())
    return {
        "trades": trades,
        "trade_units": round(units, 2),
        "fixed_per_day": round(total / days, 2),
        "fixed_per_month": round(total / days * 30, 2),
        "fixed_pf": round(gross_win / gross_loss, 3) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0),
        "sharpe_like": c["sharpe_like"],
        "max_losing_day_streak": c["max_losing_day_streak"],
        "worst_day": round(min(vals), 2) if vals else 0.0,
        "best_day": round(max(vals), 2) if vals else 0.0,
        "by_leg": by_leg,
    }


def _eval(weights, agg_by_window, windows, target_day):
    rows = []
    for days in windows:
        rows.append({"days": days, **_stats(agg_by_window[days], days, weights)})
    min_day = min(r["fixed_per_day"] for r in rows)
    avg_day = sum(r["fixed_per_day"] for r in rows) / len(rows)
    min_pf = min(r["fixed_pf"] for r in rows)
    avg_sharpe = sum(r["sharpe_like"] for r in rows) / len(rows)
    max_streak = max(r["max_losing_day_streak"] for r in rows)
    worst_day = min(r["worst_day"] for r in rows)
    scale_all = target_day / min_day if min_day > 0 else 999.0
    scaled_worst = worst_day * scale_all
    return rows, {
        "min_day": min_day,
        "avg_day": avg_day,
        "min_pf": min_pf,
        "avg_sharpe": avg_sharpe,
        "max_streak": max_streak,
        "worst_day": worst_day,
        "scale_all": scale_all,
        "scaled_worst": scaled_worst,
    }


def _score(summary):
    return (
        1 if summary["min_day"] > 0 else 0,
        1 if summary["max_streak"] <= 4 else 0,
        round(-summary["scale_all"], 4),
        round(summary["scaled_worst"], 2),
        round(summary["min_pf"], 4),
        round(summary["avg_sharpe"], 4),
    )


def _weights_label(weights):
    demo = "".join(k for k in DEMO_KEYS if weights.get(k, 0) > 0)
    allin = "_".join(f"{k}{weights[k]:g}" for k in ALLIN_KEYS if weights.get(k, 0) > 0)
    return f"D[{demo}]" + (f"+{allin}" if allin else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="90,120,150,180")
    ap.add_argument("--target-day", type=float, default=1000.0)
    ap.add_argument("--keep-demo", type=int, default=250)
    ap.add_argument("--demo-pool", type=int, default=10)
    ap.add_argument("--cache-dir", default=os.path.join(ROOT_DIR, "tmp", "s72_cache"))
    ap.add_argument("--out", default="s74_subset_search.csv")
    args = ap.parse_args()
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]

    agg_by_window = {}
    for days in windows:
        payload = _load_cache(args.cache_dir, days, DEFAULT_SPREAD)
        if payload is None:
            raise SystemExit(f"missing cache for {days}d; run optimize_s72_vs_demo_portfolio.py first")
        # Use P16 because it contains all demo legs, plus All-in-4S cache.
        agg_by_window[days] = _aggregate_normalized(payload["P16"] + payload["ALLIN"], DEFAULT_SPREAD)

    leg_rank = []
    for key in DEMO_KEYS:
        weights = {k: 0.0 for k in DEMO_KEYS + ALLIN_KEYS}
        weights[key] = 1.0
        rows, summary = _eval(weights, agg_by_window, windows, args.target_day)
        leg_rank.append((key, summary))
    leg_rank.sort(key=lambda x: (
        x[1]["min_day"],
        x[1]["min_pf"],
        x[1]["avg_sharpe"],
        x[1]["worst_day"],
    ), reverse=True)
    pool_keys = [k for k, _ in leg_rank[: max(1, min(args.demo_pool, len(leg_rank)))]]
    print("Demo pool:", ",".join(pool_keys), flush=True)

    demo_candidates = []
    for mask in range(1, 1 << len(pool_keys)):
        weights = {k: 0.0 for k in DEMO_KEYS + ALLIN_KEYS}
        for i, key in enumerate(pool_keys):
            if mask & (1 << i):
                weights[key] = 1.0
        rows, summary = _eval(weights, agg_by_window, windows, args.target_day)
        demo_candidates.append((weights, rows, summary, _score(summary)))
    demo_candidates.sort(key=lambda x: x[3], reverse=True)
    demo_candidates = demo_candidates[: args.keep_demo]

    allin_grid = list(itertools.product(
        [0.0, 4.0, 8.0, 12.0, 16.0],
        [0.0, 8.0, 16.0, 24.0, 32.0],
        [0.0, 1.0, 2.0, 4.0, 8.0],
    ))
    combos = []
    for base_weights, _, _, _ in demo_candidates:
        for w63, w69, w64 in allin_grid:
            weights = dict(base_weights)
            weights.update({"S63": w63, "S69": w69, "S64": w64})
            rows, summary = _eval(weights, agg_by_window, windows, args.target_day)
            combos.append((weights, rows, summary, _score(summary)))
    combos.sort(key=lambda x: x[3], reverse=True)

    fields = [
        "timestamp", "rank", "label", "score", "min_day", "avg_day", "min_pf",
        "avg_sharpe", "max_streak", "scale_all", "scaled_worst", "days",
        "fixed_per_day", "fixed_pf", "sharpe_like", "max_losing_day_streak",
        "worst_day", "best_day", "trade_units",
    ]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for rank, (weights, rows, summary, score) in enumerate(combos[:80], 1):
            for r in rows:
                w.writerow({
                    "timestamp": ts,
                    "rank": rank,
                    "label": _weights_label(weights),
                    "score": score,
                    "min_day": round(summary["min_day"], 2),
                    "avg_day": round(summary["avg_day"], 2),
                    "min_pf": round(summary["min_pf"], 3),
                    "avg_sharpe": round(summary["avg_sharpe"], 3),
                    "max_streak": summary["max_streak"],
                    "scale_all": round(summary["scale_all"], 3),
                    "scaled_worst": round(summary["scaled_worst"], 2),
                    "days": r["days"],
                    "fixed_per_day": r["fixed_per_day"],
                    "fixed_pf": r["fixed_pf"],
                    "sharpe_like": r["sharpe_like"],
                    "max_losing_day_streak": r["max_losing_day_streak"],
                    "worst_day": r["worst_day"],
                    "best_day": r["best_day"],
                    "trade_units": r["trade_units"],
                })

    print("Top 12 S74 subset candidates:")
    for i, (weights, rows, summary, score) in enumerate(combos[:12], 1):
        print(
            f"{i:>2}. {_weights_label(weights)} min$/d={summary['min_day']:.2f} "
            f"avg$/d={summary['avg_day']:.2f} minPF={summary['min_pf']:.2f} "
            f"scaleAll={summary['scale_all']:.2f} scaledWorst={summary['scaled_worst']:.2f} "
            f"st={summary['max_streak']} score={score}"
        )
        print("    " + " | ".join(
            f"{r['days']}d $/d={r['fixed_per_day']:.2f} PF={r['fixed_pf']:.2f} "
            f"st={r['max_losing_day_streak']} worst={r['worst_day']:.2f}" for r in rows
        ))
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
