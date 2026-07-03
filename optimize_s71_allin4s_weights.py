"""
optimize_s71_allin4s_weights.py - Weighted All-in-4S portfolio search.

RESEARCH/BACKTEST-ONLY. No live bot wiring.

Starts from S70:
- S63 Normal = base entry engine
- S69 HC = high-confidence booster
- S64 = optional yield leg

Searches fixed-lot-equivalent weights and scores robustness across multiple windows.
"""

import argparse
import csv
import itertools
import os
from datetime import datetime

import config
import sim_s31_backtest as s31sim
from sim_s70_allin4s_portfolio import DEFAULT_SPREAD, run_portfolio


def _weighted_stats(raw, days, spread, weights):
    gross_win = gross_loss = 0.0
    wins = losses = 0
    total = 0.0
    trade_units = 0.0
    by_day = {}
    by_leg = {}
    active_trades = 0
    for t in raw:
        leg = t.get("leg", "?")
        w = float(weights.get(leg, 0.0))
        if w <= 0:
            continue
        pnl = (float(t["diff_usd_per_001lot"]) - spread) * w
        total += pnl
        trade_units += w
        active_trades += 1
        if pnl > 0:
            wins += 1
            gross_win += pnl
        else:
            losses += 1
            gross_loss += abs(pnl)
        d = config.mt5_ts_to_bkk(t["exit_time_ts"]).strftime("%Y-%m-%d")
        by_day[d] = by_day.get(d, 0.0) + pnl
        by_leg[leg] = by_leg.get(leg, 0.0) + pnl
    c = s31sim.consistency_metrics(by_day) or {
        "pct_pos_days": 0.0,
        "max_losing_day_streak": 0,
        "sharpe_like": 0.0,
    }
    return {
        "trades": active_trades,
        "trade_units": round(trade_units, 2),
        "wr": round(100.0 * wins / active_trades, 1) if active_trades else 0.0,
        "fixed_pnl": round(total, 2),
        "fixed_per_day": round(total / days, 2) if days else 0.0,
        "fixed_per_month": round(total / days * 30, 2) if days else 0.0,
        "fixed_pf": round(gross_win / gross_loss, 3) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0),
        "fixed_avg": round(total / trade_units, 3) if trade_units else 0.0,
        "pct_pos_days": c["pct_pos_days"],
        "max_losing_day_streak": c["max_losing_day_streak"],
        "sharpe_like": c["sharpe_like"],
        "by_leg": by_leg,
    }


def _score(rows):
    min_pf = min(r["fixed_pf"] for r in rows)
    max_streak = max(r["max_losing_day_streak"] for r in rows)
    avg_day = sum(r["fixed_per_day"] for r in rows) / len(rows)
    avg_sharpe = sum(r["sharpe_like"] for r in rows) / len(rows)
    # Prefer robust PF/streak first, then consistency, then yield.
    return (
        1 if max_streak <= 3 else 0,
        round(min_pf, 4),
        round(avg_sharpe, 4),
        round(avg_day, 4),
        -max_streak,
    )


def _weights_label(weights):
    return "_".join(f"{k}{v:g}" for k, v in sorted(weights.items()) if v > 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="90,120,150,180")
    ap.add_argument("--out", default="s71_allin4s_weight_search.csv")
    args = ap.parse_args()
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]

    raw_by_window = {}
    for days in windows:
        print(f"fetch/replay base legs days={days} ...")
        raw_by_window[days] = run_portfolio(days, DEFAULT_SPREAD, ["S63", "S64", "S69"])

    combos = []
    for w69, w64 in itertools.product(
        [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0],
        [0.0, 0.25, 0.5, 0.75, 1.0],
    ):
        weights = {"S63": 1.0, "S69": w69, "S64": w64}
        rows = []
        for days in windows:
            s = _weighted_stats(raw_by_window[days], days, DEFAULT_SPREAD, weights)
            rows.append({"days": days, **s})
        combos.append((weights, rows, _score(rows)))

    combos.sort(key=lambda x: x[2], reverse=True)
    fields = [
        "timestamp", "rank", "label", "w_s63", "w_s69", "w_s64", "score",
        "min_pf", "avg_pf", "avg_day", "avg_month", "avg_sharpe", "max_streak",
        "days", "trades", "trade_units", "fixed_per_day", "fixed_per_month",
        "fixed_pf", "sharpe_like", "max_losing_day_streak", "by_leg",
    ]
    is_new = not os.path.exists(args.out)
    with open(args.out, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if is_new:
            w.writeheader()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for rank, (weights, rows, score) in enumerate(combos, 1):
            min_pf = min(r["fixed_pf"] for r in rows)
            avg_pf = sum(r["fixed_pf"] for r in rows) / len(rows)
            avg_day = sum(r["fixed_per_day"] for r in rows) / len(rows)
            avg_month = sum(r["fixed_per_month"] for r in rows) / len(rows)
            avg_sharpe = sum(r["sharpe_like"] for r in rows) / len(rows)
            max_streak = max(r["max_losing_day_streak"] for r in rows)
            label = _weights_label(weights)
            for r in rows:
                w.writerow({
                    "timestamp": ts,
                    "rank": rank,
                    "label": label,
                    "w_s63": weights["S63"],
                    "w_s69": weights["S69"],
                    "w_s64": weights["S64"],
                    "score": score,
                    "min_pf": round(min_pf, 3),
                    "avg_pf": round(avg_pf, 3),
                    "avg_day": round(avg_day, 3),
                    "avg_month": round(avg_month, 2),
                    "avg_sharpe": round(avg_sharpe, 3),
                    "max_streak": max_streak,
                    "days": r["days"],
                    "trades": r["trades"],
                    "trade_units": r["trade_units"],
                    "fixed_per_day": r["fixed_per_day"],
                    "fixed_per_month": r["fixed_per_month"],
                    "fixed_pf": r["fixed_pf"],
                    "sharpe_like": r["sharpe_like"],
                    "max_losing_day_streak": r["max_losing_day_streak"],
                    "by_leg": ";".join(f"{k}:{v:.2f}" for k, v in sorted(r["by_leg"].items())),
                })

    print("\nTop 12 weighted candidates:")
    for i, (weights, rows, score) in enumerate(combos[:12], 1):
        min_pf = min(r["fixed_pf"] for r in rows)
        avg_day = sum(r["fixed_per_day"] for r in rows) / len(rows)
        avg_month = sum(r["fixed_per_month"] for r in rows) / len(rows)
        avg_sharpe = sum(r["sharpe_like"] for r in rows) / len(rows)
        max_streak = max(r["max_losing_day_streak"] for r in rows)
        print(
            f"{i:>2}. {_weights_label(weights)} minPF={min_pf:.3f} "
            f"avg$/d={avg_day:.2f} avg$/mo={avg_month:.2f} "
            f"avgSharpe={avg_sharpe:.3f} maxStreak={max_streak} score={score}"
        )
        print("    " + " | ".join(
            f"{r['days']}d PF={r['fixed_pf']:.2f} $/d={r['fixed_per_day']:.2f} "
            f"st={r['max_losing_day_streak']}" for r in rows
        ))
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
