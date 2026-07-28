# -*- coding: utf-8 -*-
"""Exact cached payoff and breakeven sweep for S288."""

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
from strategy288 import detect_s288
from sweep_s235_payoff import _summary_market


BROAD_RR = tuple(round(7.0 + 0.5 * index, 1) for index in range(67))
BROAD_BE = tuple(round(0.20 + 0.05 * index, 2) for index in range(37))
FINE_RR = tuple(round(7.0 + 0.1 * index, 1) for index in range(331))
FINE_BE = tuple(round(0.20 + 0.02 * index, 2) for index in range(91))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument("--stage", choices=("broad", "fine"), default="broad")
    parser.add_argument("--top", type=int, default=40)
    parser.add_argument("--rr-min", type=float)
    parser.add_argument("--rr-max", type=float)
    parser.add_argument("--be-min", type=float)
    parser.add_argument("--be-max", type=float)
    args = parser.parse_args()
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    lookback = 300
    bars, start_bkk, start_index = prepare_rates(
        args.months, "M5", end, lookback
    )
    base_cfg = {"TP_RR": 10.0, "BE_RR": 1.0}
    cached = {}
    for index in range(start_index, len(bars) - 1):
        window = bars[index - lookback + 1:index + 1]
        dt_bkk = datetime.fromtimestamp(int(bars[index]["time"]), tz=BKK)
        signal = detect_s288(window, "M5", dt_bkk, base_cfg)
        validate_signal(signal, 288)
        cached[index] = signal

    rr_values = FINE_RR if args.stage == "fine" else BROAD_RR
    be_values = FINE_BE if args.stage == "fine" else BROAD_BE
    if args.rr_min is not None:
        rr_values = tuple(value for value in rr_values if value >= args.rr_min)
    if args.rr_max is not None:
        rr_values = tuple(value for value in rr_values if value <= args.rr_max)
    if args.be_min is not None:
        be_values = tuple(value for value in be_values if value >= args.be_min)
    if args.be_max is not None:
        be_values = tuple(value for value in be_values if value <= args.be_max)
    rows = [
        _summary_market(rr, be, bars, start_index, cached)
        for rr in rr_values
        for be in be_values
    ]
    official, _ = backtest(
        288,
        args.months,
        "M5",
        0.20,
        0.01,
        end,
        lookback,
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
