# -*- coding: utf-8 -*-
"""Reproducible robustness checks for the MQ5-parity EA2 model."""

from __future__ import annotations

import argparse
import json
import random
from datetime import timedelta
from pathlib import Path

import MetaTrader5 as mt5

from backtest_ea2 import BKK, bkk_to_query, fmt_bkk, parse_bkk, prepare_rates
from ea_strategy_2 import DEFAULT_CFG, run_backtest


HERE = Path(__file__).resolve().parent


def metrics(trades):
    profits = [float(t["profit"]) for t in trades]
    gross_win = sum(p for p in profits if p > 0)
    gross_loss = -sum(p for p in profits if p < 0)
    equity = peak = max_dd = 0.0
    for pnl in profits:
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return {
        "trades": len(profits), "wins": sum(p > 0 for p in profits),
        "win_rate": round(sum(p > 0 for p in profits) / len(profits) * 100, 2) if profits else None,
        "pnl": round(sum(profits), 2),
        "profit_factor": round(gross_win / gross_loss, 3) if gross_loss else None,
        "max_drawdown": round(max_dd, 2),
    }


def monte_carlo(profits, samples=1000, seed=435):
    rng = random.Random(seed)
    nets, dds = [], []
    for _ in range(samples):
        path = [rng.choice(profits) for _ in profits]
        equity = peak = dd = 0.0
        for pnl in path:
            equity += pnl
            peak = max(peak, equity)
            dd = max(dd, peak - equity)
        nets.append(equity)
        dds.append(dd)
    nets.sort(); dds.sort()
    return {
        "samples": samples,
        "p05_net": round(nets[int(samples * 0.05)], 2),
        "median_net": round(nets[samples // 2], 2),
        "p95_drawdown": round(dds[int(samples * 0.95)], 2),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--end", default="")
    parser.add_argument("--output", default=str(HERE / "ea2_validation_365d.json"))
    args = parser.parse_args()
    end = parse_bkk(args.end)
    start = end - timedelta(days=args.days)
    cfg = dict(DEFAULT_CFG)
    m1, start_bar = prepare_rates("M1", start, end, cfg)
    candidate, _ = run_backtest(m1, cfg, spread=0.20, contract_multiplier=1.0, start_bar=start_bar)
    start_ts = int(bkk_to_query(start).timestamp())
    end_ts = int(bkk_to_query(end).timestamp())
    candidate = [t for t in candidate if start_ts <= int(m1[t["entry_bar"]]["time"]) < end_ts]
    midpoint = start_ts + (end_ts - start_ts) // 2
    halves = {
        "first": metrics([t for t in candidate if int(m1[t["entry_bar"]]["time"]) < midpoint]),
        "second_oos": metrics([t for t in candidate if int(m1[t["entry_bar"]]["time"]) >= midpoint]),
    }
    quarter = (end_ts - start_ts) // 4
    walk_forward = {}
    for i in range(4):
        lo = start_ts + quarter * i
        hi = end_ts if i == 3 else lo + quarter
        walk_forward[f"q{i + 1}"] = metrics([
            t for t in candidate if lo <= int(m1[t["entry_bar"]]["time"]) < hi
        ])

    stress = {}
    for spread in (0.20, 0.30, 0.40):
        trades, _ = run_backtest(
            m1, cfg, spread=spread, contract_multiplier=1.0,
            start_bar=start_bar,
        )
        trades = [t for t in trades if start_ts <= int(m1[t["entry_bar"]]["time"]) < end_ts]
        stress[f"spread_{spread:.2f}"] = metrics(trades)

    candidate_metrics = metrics(candidate)
    profits = [float(t["profit"]) for t in candidate]
    mc = monte_carlo(profits) if profits else {}
    checks = {
        "profit_factor_above_1": (candidate_metrics["profit_factor"] or 0) > 1,
        "both_split_halves_profitable": halves["first"]["pnl"] > 0 and halves["second_oos"]["pnl"] > 0,
        "all_walk_forward_quarters_profitable": all(v["pnl"] > 0 for v in walk_forward.values()),
        "spread_0_40_profitable": stress["spread_0.40"]["pnl"] > 0,
        "monte_carlo_p05_profitable": bool(mc) and mc["p05_net"] > 0,
    }
    report = {
        "period": {"start_bkk": fmt_bkk(start), "end_bkk": fmt_bkk(end)},
        "model": "M1 Thirakorn SMC MQ5 defaults: fixed 200/600pt SL/TP, fixed BE/trailing, no HTF/ATR gates",
        "candidate": candidate_metrics,
        "split_half": halves, "walk_forward_quarters": walk_forward,
        "spread_stress": stress, "monte_carlo": mc, "checks": checks,
        "all_checks_pass": all(checks.values()),
        "limitations": [
            "OHLC deterministic intrabar path, not MT5 real-tick execution",
            "spread is modeled; real slippage, commission, swaps and rejected modifications are not included",
            "demo soak and restart/disconnect drills require live elapsed time",
        ],
    }
    Path(args.output).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
