# -*- coding: utf-8 -*-
"""Cached AD/tail-imbalance threshold sensitivity for S300 BUY signals."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import re

from sim_strategy_backtest import BKK, parse_bkk, prepare_rates, validate_signal
from strategy197 import _wait
from strategy300 import detect_s300
from sweep_s235_payoff import _summary_market


_SHAPE_PATTERN = re.compile(
    r"AD=([0-9]+(?:\.[0-9]+)?), tail-energy imbalance=(-?[0-9]+(?:\.[0-9]+)?)"
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument(
        "--ad-values",
        default="0,0.50,0.75,1.00,1.25,1.50,2.00",
    )
    parser.add_argument(
        "--imbalance-values",
        default="0,0.05,0.10,0.15,0.20,0.25,0.30",
    )
    args = parser.parse_args()
    ad_values = tuple(float(value) for value in args.ad_values.split(","))
    imbalance_values = tuple(
        float(value) for value in args.imbalance_values.split(",")
    )
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    bars, _, start_index = prepare_rates(args.months, "M5", end, 300)
    raw = {}
    for index in range(start_index, len(bars) - 1):
        window = bars[index - 299:index + 1]
        dt_bkk = datetime.fromtimestamp(int(bars[index]["time"]), tz=BKK)
        signal = detect_s300(
            window,
            "M5",
            dt_bkk,
            {
                "ALLOW_BUY": True,
                "ALLOW_SELL": False,
                "ANDERSON_DARLING_MIN": 0.0,
                "TAIL_IMBALANCE_MIN": 0.0,
                "TP_RR": 12.0,
                "BE_RR": 0.50,
            },
        )
        validate_signal(signal, 300)
        raw[index] = signal
    for ad_min in ad_values:
        for imbalance_min in imbalance_values:
            cached = {}
            for index, signal in raw.items():
                if signal["signal"] not in ("BUY", "SELL"):
                    cached[index] = signal
                    continue
                match = _SHAPE_PATTERN.search(signal["reason"])
                if match is None:
                    raise AssertionError(signal)
                statistic, imbalance = map(float, match.groups())
                cached[index] = (
                    signal
                    if statistic >= ad_min and imbalance >= imbalance_min
                    else _wait("Filtered by S300 threshold sensitivity")
                )
            result = _summary_market(
                12.0,
                0.50,
                bars,
                start_index,
                cached,
            )
            print(
                json.dumps(
                    {
                        "months": args.months,
                        "ad": ad_min,
                        "imbalance": imbalance_min,
                        **result,
                    },
                    allow_nan=True,
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
