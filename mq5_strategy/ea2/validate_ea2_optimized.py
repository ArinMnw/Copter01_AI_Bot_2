# -*- coding: utf-8 -*-
"""All-timeframe OOS and execution-cost stress for optimized EA2 inputs."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

from backtest_ea2 import TF_ORDER, fmt_bkk, parse_bkk, prepare_rates
from ea_strategy_2 import DEFAULT_CFG
from optimize_ea2_inputs import evaluate


HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--end", default="2026-10-06T21:57:03+07:00")
    parser.add_argument("--source", default=str(HERE / "ea2_optimization_tp_boundary.json"))
    parser.add_argument("--output", default=str(HERE / "ea2_optimized_validation.json"))
    args = parser.parse_args()

    end = parse_bkk(args.end)
    start = end - timedelta(days=args.days)
    midpoint = start + (end - start) / 2
    source = json.loads(Path(args.source).read_text(encoding="utf-8"))
    raw_cfg = dict(DEFAULT_CFG)
    raw_cfg.update(source["best"]["config"])
    practical_cfg = deepcopy(raw_cfg)
    practical_cfg.update({
        "TP_POINTS": 5000,
        "TRAIL_STEP_POINTS": 5,
        "OB_PREFER_DEEPER_MAX_POINTS": 100,
    })

    preload = dict(DEFAULT_CFG)
    preload["MAX_BARS_LOOKBACK"] = 1000
    print(f"Loading all TF data: {fmt_bkk(start)} -> {fmt_bkk(end)}", flush=True)
    datasets = {tf: prepare_rates(tf, start, end, preload) for tf in TF_ORDER}
    scenarios = (
        ("full_base", start, end, 0.20, 0, 0.0),
        ("first_half", start, midpoint, 0.20, 0, 0.0),
        ("second_half", midpoint, end, 0.20, 0, 0.0),
        ("spread_30", start, end, 0.30, 0, 0.0),
        ("spread_40", start, end, 0.40, 0, 0.0),
        ("spread_50", start, end, 0.50, 0, 0.0),
        ("slippage_10", start, end, 0.20, 10, 0.0),
        ("slippage_20", start, end, 0.20, 20, 0.0),
        ("commission_7", start, end, 0.20, 0, 7.0),
        ("adverse_costs", start, end, 0.40, 10, 7.0),
    )
    report = {
        "period": {"start_bkk": fmt_bkk(start), "end_bkk": fmt_bkk(end)},
        "configs": {},
    }
    for config_name, base_cfg in (("raw_best", raw_cfg), ("practical", practical_cfg)):
        item = {"config": base_cfg, "scenarios": {}}
        for scenario, lo, hi, spread, slippage, commission in scenarios:
            cfg = deepcopy(base_cfg)
            cfg["SLIPPAGE_POINTS"] = slippage
            cfg["COMMISSION_PER_LOT_USD"] = commission
            result = evaluate(cfg, datasets, lo, hi, spread, 0.01)
            item["scenarios"][scenario] = {
                "period": {"start_bkk": fmt_bkk(lo), "end_bkk": fmt_bkk(hi)},
                "spread": spread,
                "slippage_points": slippage,
                "commission_per_lot_usd": commission,
                **result,
            }
            print(
                f"{config_name}/{scenario}: net={result['combined']['net_profit']:.2f} "
                f"dd={result['combined']['max_drawdown']:.2f} "
                f"PF={result['combined']['profit_factor']} +TF={result['profitable_tfs']}",
                flush=True,
            )
        report["configs"][config_name] = item
        Path(args.output).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
        )
    print(f"DONE output={args.output}", flush=True)


if __name__ == "__main__":
    main()
