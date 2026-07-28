# -*- coding: utf-8 -*-
"""Cached KS/median-shift threshold sensitivity for S302 SELL signals."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import re

from sim_strategy_backtest import BKK, parse_bkk, prepare_rates, validate_signal
from strategy197 import _wait
from strategy302 import detect_s302
from sweep_s235_payoff import _summary_market


_SHIFT_PATTERN = re.compile(
    r"KSz=([0-9]+(?:\.[0-9]+)?), median shift=(-?[0-9]+(?:\.[0-9]+)?)MAD"
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument(
        "--ks-values",
        default="0,0.50,0.75,1.00,1.05,1.10,1.15,1.25,1.50",
    )
    parser.add_argument(
        "--shift-values",
        default="0,0.10,0.20,0.40,0.60,0.80,1.00",
    )
    args = parser.parse_args()
    ks_values = tuple(float(value) for value in args.ks_values.split(","))
    shift_values = tuple(float(value) for value in args.shift_values.split(","))
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    bars, _, start_index = prepare_rates(args.months, "M5", end, 300)
    raw = {}
    for index in range(start_index, len(bars) - 1):
        window = bars[index - 299:index + 1]
        dt_bkk = datetime.fromtimestamp(int(bars[index]["time"]), tz=BKK)
        signal = detect_s302(
            window,
            "M5",
            dt_bkk,
            {
                "ALLOW_BUY": False,
                "ALLOW_SELL": True,
                "KS_SCALED_MIN": 0.0,
                "MEDIAN_SHIFT_MAD_MIN": 0.0,
                "TP_RR": 26.3,
                "BE_RR": 0.95,
            },
        )
        validate_signal(signal, 302)
        raw[index] = signal
    for ks_min in ks_values:
        for shift_min in shift_values:
            cached = {}
            for index, signal in raw.items():
                if signal["signal"] not in ("BUY", "SELL"):
                    cached[index] = signal
                    continue
                match = _SHIFT_PATTERN.search(signal["reason"])
                if match is None:
                    raise AssertionError(signal)
                statistic, shift = map(float, match.groups())
                cached[index] = (
                    signal
                    if statistic >= ks_min and abs(shift) >= shift_min
                    else _wait("Filtered by S302 threshold sensitivity")
                )
            result = _summary_market(
                26.3,
                0.95,
                bars,
                start_index,
                cached,
            )
            print(
                json.dumps(
                    {
                        "months": args.months,
                        "ks": ks_min,
                        "shift": shift_min,
                        **result,
                    },
                    allow_nan=True,
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
