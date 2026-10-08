# -*- coding: utf-8 -*-
"""Coordinate-search MQ5 trading inputs with a full 365-day, all-TF test per trial."""

from __future__ import annotations

import argparse
import json
import math
import time
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

from backtest_ea2 import (
    TF_ORDER,
    bar_time_to_bkk,
    fmt_bkk,
    parse_bkk,
    prepare_rates,
)
from ea_strategy_2 import DEFAULT_CFG, run_backtest


HERE = Path(__file__).resolve().parent


SEARCH_SPACE = (
    ("SL_POINTS", (100, 150, 200, 250, 300, 400, 500, 600)),
    ("TP_POINTS", (200, 300, 400, 600, 800, 1000, 1200, 1500)),
    ("USE_BREAKEVEN", (True, False)),
    ("BREAKEVEN_TRIGGER_POINTS", (75, 100, 150, 200, 250, 300)),
    ("BREAKEVEN_LOCK_POINTS", (0, 10, 25, 50, 75)),
    ("USE_TRAILING", (True, False)),
    ("TRAIL_TRIGGER_POINTS", (100, 150, 200, 250, 300, 400)),
    ("TRAIL_DISTANCE_POINTS", (100, 150, 200, 300, 400, 500)),
    ("TRAIL_STEP_POINTS", (5, 10, 25, 50, 100)),
    ("SWING_BARS", (1, 2, 3, 4, 5)),
    ("BOS_CONFIRM_COUNT", (1, 2, 3)),
    ("MAX_BARS_LOOKBACK", (200, 300, 500, 750, 1000)),
    ("ENTER_ON_BOS_CONFIRM", (False, True)),
    ("ONE_TRADE_PER_CYCLE", (True, False)),
    ("USE_FIB_OB_FILTER", (True, False)),
    ("OB_SEARCH_MAX_BARS", (5, 10, 20, 30, 50)),
    ("ENABLE_OB_RETEST_ENTRY", (True, False)),
    ("OB_MIN_BARS_BEFORE_RETEST", (1, 2, 3, 5, 8)),
    ("MIN_LEG_POINTS", (0, 50, 100, 150, 200, 300)),
    ("OB_MAX_BARS_VALID", (20, 35, 50, 75, 100, 0)),
    ("OB_PREFER_DEEPER_MAX_POINTS", (0, 100, 200, 300, 500)),
    ("MAX_OPEN_POSITIONS", (1, 2, 3, 4)),
    ("SESSION_START_HOUR", (0, 6, 8, 10, 12)),
    ("SESSION_END_HOUR", (18, 20, 22, 24)),
)

REFINE_SPACE = (
    ("SL_POINTS", (1200, 1500, 2000, 3000)),
    ("TP_POINTS", (1000, 1500, 2000, 3000, 5000, 7500, 10000, 20000)),
    ("BREAKEVEN_TRIGGER_POINTS", (60, 75, 90, 100)),
    ("BREAKEVEN_LOCK_POINTS", (10, 15, 25)),
    ("TRAIL_TRIGGER_POINTS", (75, 100, 125, 150)),
    ("TRAIL_DISTANCE_POINTS", (75, 100, 125)),
    ("TRAIL_STEP_POINTS", (1, 5, 10)),
    ("OB_SEARCH_MAX_BARS", (3, 5, 7, 10)),
    ("MIN_LEG_POINTS", (175, 200, 225, 250)),
    ("OB_MAX_BARS_VALID", (0, 100, 150, 200)),
    ("OB_PREFER_DEEPER_MAX_POINTS", (0, 100, 200, 300)),
)


def _metrics(profits: list[float]) -> dict:
    gross_win = sum(p for p in profits if p > 0)
    gross_loss = -sum(p for p in profits if p < 0)
    equity = peak = max_dd = 0.0
    for pnl in profits:
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return {
        "net_profit": round(sum(profits), 6),
        "max_drawdown": round(max_dd, 6),
        "profit_factor": round(gross_win / gross_loss, 6) if gross_loss else None,
        "trades": len(profits),
        "wins": sum(p > 0 for p in profits),
    }


def _score(per_tf: dict, combined: dict, objective: str = "portfolio") -> float:
    traded = [v for v in per_tf.values() if v["trades"]]
    profitable = sum(v["net_profit"] > 0 for v in traded)
    negative = sum(v["net_profit"] < 0 for v in traded)
    if objective == "m1":
        m1 = per_tf["M1"]
        return round(
            m1["net_profit"] / max(m1["max_drawdown"], 1.0)
            + profitable * 0.05 - negative * 0.05,
            9,
        )
    calmar = combined["net_profit"] / max(combined["max_drawdown"], 1.0)
    # Combined portfolio return/DD is primary; breadth prevents one TF from
    # winning while most timeframes deteriorate.
    return round(calmar + profitable * 0.15 - negative * 0.25, 9)


def _valid_cfg(cfg: dict) -> bool:
    # A BE stop at/near current price is rejected by many brokers because of
    # stop/freeze levels.  Keep at least 50 points between trigger and lock,
    # matching the source EA's maximum accepted-spread budget.
    if bool(cfg["USE_BREAKEVEN"]):
        if float(cfg["BREAKEVEN_LOCK_POINTS"]) > float(cfg["BREAKEVEN_TRIGGER_POINTS"]) - 50:
            return False
    return int(cfg["SESSION_START_HOUR"]) != int(cfg["SESSION_END_HOUR"])


def evaluate(
    cfg: dict, datasets: dict, start_bkk, end_bkk, spread: float, lot: float,
    objective: str = "portfolio",
) -> dict:
    per_tf = {}
    combined_events = []
    start_ts = int((start_bkk + timedelta(hours=1)).timestamp())
    end_ts = int((end_bkk + timedelta(hours=1)).timestamp())
    for tf in TF_ORDER:
        bars, start_bar = datasets[tf]
        trades, _ = run_backtest(
            bars, cfg, spread=spread, contract_multiplier=100.0 * lot, start_bar=start_bar
        )
        selected = [
            trade for trade in trades
            if start_ts <= int(bars[trade["entry_bar"]]["time"]) < end_ts
        ]
        profits = [float(trade["profit"]) for trade in selected]
        per_tf[tf] = _metrics(profits)
        combined_events.extend(
            (int(bars[trade["exit_bar"]]["time"]), float(trade["profit"]))
            for trade in selected
        )
    combined_events.sort(key=lambda item: item[0])
    combined = _metrics([pnl for _, pnl in combined_events])
    result = {"per_tf": per_tf, "combined": combined}
    result["profitable_tfs"] = sum(
        value["trades"] > 0 and value["net_profit"] > 0 for value in per_tf.values()
    )
    result["score"] = _score(per_tf, combined, objective)
    return result


def _write_checkpoint(path: Path, report: dict) -> None:
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--end", default="2026-10-06T21:57:03+07:00")
    parser.add_argument("--spread", type=float, default=0.20)
    parser.add_argument("--lot", type=float, default=0.01)
    parser.add_argument("--passes", type=int, default=1)
    parser.add_argument("--start-cfg-json", default="{}")
    parser.add_argument("--start-after", default="")
    parser.add_argument("--refine", action="store_true")
    parser.add_argument("--only", default="")
    parser.add_argument("--objective", choices=("portfolio", "m1"), default="portfolio")
    parser.add_argument("--output", default=str(HERE / "ea2_optimization_365d_all_tf.json"))
    args = parser.parse_args()

    end_bkk = parse_bkk(args.end)
    start_bkk = end_bkk - timedelta(days=args.days)
    preload_cfg = dict(DEFAULT_CFG)
    preload_cfg["MAX_BARS_LOOKBACK"] = max(1000, int(preload_cfg["MAX_BARS_LOOKBACK"]))
    print(f"Loading all TF data: {fmt_bkk(start_bkk)} -> {fmt_bkk(end_bkk)}", flush=True)
    datasets = {tf: prepare_rates(tf, start_bkk, end_bkk, preload_cfg) for tf in TF_ORDER}

    cfg = dict(DEFAULT_CFG)
    cfg.update(json.loads(args.start_cfg_json))
    if not _valid_cfg(cfg):
        parser.error("start config violates live-execution constraints")
    report = {
        "method": "greedy coordinate search; every trial is a 365-day backtest on all 8 TFs",
        "selection": (
            "M1 net/max-drawdown plus all-TF breadth"
            if args.objective == "m1"
            else "combined chronological net/max-drawdown plus profitable-TF breadth"
        ),
        "period": {"start_bkk": fmt_bkk(start_bkk), "end_bkk": fmt_bkk(end_bkk)},
        "spread": args.spread,
        "lot": args.lot,
        "trials": [],
    }
    output = Path(args.output)
    started = time.time()

    baseline = evaluate(cfg, datasets, start_bkk, end_bkk, args.spread, args.lot, args.objective)
    report["baseline"] = {"config": deepcopy(cfg), **baseline}
    best = baseline
    print(
        f"BASE score={best['score']:.4f} net={best['combined']['net_profit']:.2f} "
        f"dd={best['combined']['max_drawdown']:.2f} +TF={best['profitable_tfs']}", flush=True
    )
    _write_checkpoint(output, report)

    trial_id = 0
    search_space = list(REFINE_SPACE if args.refine else SEARCH_SPACE)
    if args.only:
        search_space = [(name, values) for name, values in search_space if name == args.only]
        if not search_space:
            parser.error(f"unknown --only parameter: {args.only}")
    if args.start_after:
        names = [name for name, _ in search_space]
        if args.start_after not in names:
            parser.error(f"unknown --start-after parameter: {args.start_after}")
        search_space = search_space[names.index(args.start_after) + 1:]
    for pass_no in range(1, max(1, args.passes) + 1):
        for name, values in search_space:
            incumbent_cfg = deepcopy(cfg)
            incumbent_result = best
            parameter_best_cfg = incumbent_cfg
            parameter_best = incumbent_result
            for value in values:
                if value == incumbent_cfg[name]:
                    continue
                trial_id += 1
                candidate_cfg = deepcopy(incumbent_cfg)
                candidate_cfg[name] = value
                if not _valid_cfg(candidate_cfg):
                    print(f"SKIP {name}={value!r} (live constraint)", flush=True)
                    continue
                t0 = time.time()
                result = evaluate(
                    candidate_cfg, datasets, start_bkk, end_bkk,
                    args.spread, args.lot, args.objective,
                )
                trial = {
                    "id": trial_id,
                    "pass": pass_no,
                    "parameter": name,
                    "value": value,
                    "base_value": incumbent_cfg[name],
                    "elapsed_sec": round(time.time() - t0, 3),
                    **result,
                }
                report["trials"].append(trial)
                if result["score"] > parameter_best["score"]:
                    parameter_best = result
                    parameter_best_cfg = candidate_cfg
                print(
                    f"#{trial_id:03d} {name}={value!r} score={result['score']:.4f} "
                    f"net={result['combined']['net_profit']:.2f} "
                    f"dd={result['combined']['max_drawdown']:.2f} "
                    f"+TF={result['profitable_tfs']} {trial['elapsed_sec']:.1f}s",
                    flush=True,
                )
                report["current_best"] = {"config": deepcopy(cfg), **best}
                _write_checkpoint(output, report)
            if parameter_best["score"] > incumbent_result["score"]:
                cfg = parameter_best_cfg
                best = parameter_best
                print(f"ACCEPT {name}={cfg[name]!r} score={best['score']:.4f}", flush=True)
            else:
                print(f"KEEP {name}={cfg[name]!r}", flush=True)

    report["best"] = {"config": cfg, **best}
    report["elapsed_sec"] = round(time.time() - started, 3)
    report["trial_count"] = trial_id
    _write_checkpoint(output, report)
    print(f"DONE trials={trial_id} output={output}", flush=True)


if __name__ == "__main__":
    main()
