# -*- coding: utf-8 -*-
"""Fast exact payoff and breakeven sweep for S240."""

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
from strategy240 import detect_s240
from sweep_s235_payoff import _summary_market


RR_VALUES = (41.9, 42.0, 42.1, 42.2)
BE_VALUES = (0.01, 0.02, 0.03, 0.04, 0.05, 0.06)
CASES = tuple((rr, be) for rr in RR_VALUES for be in BE_VALUES) + ((10.0, 1.0),)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=2)
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
        signal = detect_s240(window, "M5", dt_bkk, base_cfg)
        validate_signal(signal, 240)
        cached[index] = signal
    rows = [
        _summary_market(rr, be, bars, start_index, cached)
        for rr, be in CASES
    ]
    official, _ = backtest(
        240,
        args.months,
        "M5",
        0.20,
        0.01,
        end,
        lookback,
        cfg=base_cfg,
        prepared=(bars, start_bkk, start_index),
    )
    base = next(row for row in rows if row["rr"] == 10.0 and row["be"] == 1.0)
    if (
        base["closed"] != official["closed"]
        or abs(base["net"] - official["net_profit"]) > 1e-7
    ):
        raise AssertionError({"cached_base": base, "official": official})
    rows.sort(key=lambda row: (row["net"], -row["max_dd"]), reverse=True)
    for row in rows:
        print(json.dumps(row, allow_nan=True), flush=True)


if __name__ == "__main__":
    main()
