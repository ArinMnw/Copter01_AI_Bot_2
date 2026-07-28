# -*- coding: utf-8 -*-
"""Exact cached payoff/BE sweep for S301 SELL market signals."""

from __future__ import annotations

import argparse
from datetime import datetime
import json

from sim_strategy_backtest import (
    BKK,
    backtest,
    parse_bkk,
    prepare_rates,
    validate_signal,
)
from strategy301 import detect_s301
from sweep_s235_payoff import _summary_market


RR_VALUES = tuple(round(7.0 + 0.5 * index, 1) for index in range(107))
BE_VALUES = tuple(round(0.20 + 0.05 * index, 2) for index in range(37))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument("--top", type=int, default=40)
    parser.add_argument("--rr-values")
    parser.add_argument("--be-values")
    args = parser.parse_args()
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    bars, start_bkk, start_index = prepare_rates(
        args.months,
        "M5",
        end,
        300,
    )
    base_cfg = {
        "ALLOW_BUY": False,
        "ALLOW_SELL": True,
        "TP_RR": 10.0,
        "BE_RR": 1.0,
    }
    cached = {}
    for index in range(start_index, len(bars) - 1):
        window = bars[index - 299:index + 1]
        dt_bkk = datetime.fromtimestamp(int(bars[index]["time"]), tz=BKK)
        signal = detect_s301(window, "M5", dt_bkk, base_cfg)
        validate_signal(signal, 301)
        cached[index] = signal
    rr_values = RR_VALUES
    be_values = BE_VALUES
    if args.rr_values:
        rr_values = tuple(float(value) for value in args.rr_values.split(","))
    if args.be_values:
        be_values = tuple(float(value) for value in args.be_values.split(","))
    rows = [
        _summary_market(rr, be, bars, start_index, cached)
        for rr in rr_values
        for be in be_values
    ]
    official, _ = backtest(
        301,
        args.months,
        "M5",
        0.20,
        0.01,
        end,
        300,
        cfg=base_cfg,
        prepared=(bars, start_bkk, start_index),
    )
    base = _summary_market(10.0, 1.0, bars, start_index, cached)
    if (
        base["closed"] != official["closed"]
        or abs(base["net"] - official["net_profit"]) > 1e-7
    ):
        raise AssertionError({"cached_base": base, "official": official})
    rows.sort(
        key=lambda row: (row["net"], row["wins"], -row["max_dd"]),
        reverse=True,
    )
    for row in rows[:max(1, args.top)]:
        print(json.dumps(row, allow_nan=True), flush=True)


if __name__ == "__main__":
    main()
