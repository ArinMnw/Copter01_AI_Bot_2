# -*- coding: utf-8 -*-
"""Cached Sup-Chow threshold and direction sensitivity for S295."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import re

from sim_strategy_backtest import BKK, parse_bkk, prepare_rates, validate_signal
from strategy197 import _wait
from strategy295 import detect_s295
from sweep_s235_payoff import _summary_market


_F_PATTERN = re.compile(r"\bF=([0-9]+(?:\.[0-9]+)?)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument("--values", default="0,2,3,5,7,10,15,20")
    args = parser.parse_args()
    thresholds = tuple(float(value) for value in args.values.split(","))
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    bars, _, start_index = prepare_rates(args.months, "M5", end, 300)
    raw = {}
    for index in range(start_index, len(bars) - 1):
        window = bars[index - 299:index + 1]
        dt_bkk = datetime.fromtimestamp(int(bars[index]["time"]), tz=BKK)
        signal = detect_s295(
            window,
            "M5",
            dt_bkk,
            {"SUP_CHOW_F_MIN": 0.0},
        )
        validate_signal(signal, 295)
        raw[index] = signal
    for side in ("both", "buy", "sell"):
        for threshold in thresholds:
            cached = {}
            for index, signal in raw.items():
                if signal["signal"] not in ("BUY", "SELL"):
                    cached[index] = signal
                    continue
                match = _F_PATTERN.search(signal["reason"])
                if match is None:
                    raise AssertionError(signal)
                f_stat = float(match.group(1))
                side_ok = (
                    side == "both"
                    or signal["signal"].lower() == side
                )
                cached[index] = (
                    signal
                    if side_ok and f_stat >= threshold
                    else _wait("Filtered by Sup-Chow sensitivity")
                )
            result = _summary_market(
                10.0,
                1.0,
                bars,
                start_index,
                cached,
            )
            print(
                json.dumps(
                    {
                        "months": args.months,
                        "side": side,
                        "threshold": threshold,
                        **result,
                    },
                    allow_nan=True,
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
