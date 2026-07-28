# -*- coding: utf-8 -*-
"""Bounded one-factor robustness search for S158."""

from __future__ import annotations

import argparse
import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


CASES = (
    ("default", {}),
    ("jump_2.5", {"JUMP_SIGMA_MIN": 2.50}),
    ("jump_3.5", {"JUMP_SIGMA_MIN": 3.50}),
    ("volume_q70", {"JUMP_VOLUME_QUANTILE": 0.70}),
    ("volume_q90", {"JUMP_VOLUME_QUANTILE": 0.90}),
    ("retrace_382", {"ACCEPTANCE_RETRACE_MAX": 0.382}),
    ("retrace_618", {"ACCEPTANCE_RETRACE_MAX": 0.618}),
    ("confirm_60", {"CONFIRM_CLOSE_FRACTION": 0.60}),
    ("confirm_80", {"CONFIRM_CLOSE_FRACTION": 0.80}),
    ("entry_382", {"ENTRY_RANGE_FRACTION": 0.382}),
    ("entry_618", {"ENTRY_RANGE_FRACTION": 0.618}),
    ("be_075", {"BE_RR": 0.75}),
    ("be_125", {"BE_RR": 1.25}),
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=2)
    args = parser.parse_args()
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    prepared = prepare_rates(args.months, "M5", end, 300)
    rows = []
    for name, cfg in CASES:
        summary, _ = backtest(158, args.months, "M5", 0.20, 0.01, end, 300,
                              cfg=cfg, prepared=prepared)
        rows.append({
            "case": name,
            "cfg": cfg,
            "signals": summary["signals"],
            "closed": summary["closed"],
            "wins": summary["wins"],
            "win_rate": summary["win_rate"],
            "net": summary["net_profit"],
            "pf": summary["profit_factor"],
            "max_dd": summary["max_drawdown"],
        })
    rows.sort(key=lambda row: (row["net"], row["closed"], -row["max_dd"]), reverse=True)
    for row in rows:
        print(json.dumps(row, allow_nan=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
