# -*- coding: utf-8 -*-
"""Cached Gini/top-share threshold sensitivity for S299 SELL signals."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import re

from sim_strategy_backtest import BKK, parse_bkk, prepare_rates, validate_signal
from strategy197 import _wait
from strategy299 import detect_s299
from sweep_s235_payoff import _summary_market


_SHAPE_PATTERN = re.compile(
    r"Gini=([0-9]+(?:\.[0-9]+)?), top-quartile share=([0-9]+(?:\.[0-9]+)?)"
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument("--gini-values", default="0,0.30,0.35,0.40,0.45,0.50")
    parser.add_argument("--share-values", default="0,0.40,0.45,0.50,0.55,0.60")
    args = parser.parse_args()
    gini_values = tuple(float(value) for value in args.gini_values.split(","))
    share_values = tuple(float(value) for value in args.share_values.split(","))
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    bars, _, start_index = prepare_rates(args.months, "M5", end, 300)
    raw = {}
    for index in range(start_index, len(bars) - 1):
        window = bars[index - 299:index + 1]
        dt_bkk = datetime.fromtimestamp(int(bars[index]["time"]), tz=BKK)
        signal = detect_s299(
            window,
            "M5",
            dt_bkk,
            {
                "ALLOW_BUY": False,
                "ALLOW_SELL": True,
                "GINI_MIN": 0.0,
                "TOP_QUARTILE_SHARE_MIN": 0.0,
            },
        )
        validate_signal(signal, 299)
        raw[index] = signal
    for gini_min in gini_values:
        for share_min in share_values:
            cached = {}
            for index, signal in raw.items():
                if signal["signal"] not in ("BUY", "SELL"):
                    cached[index] = signal
                    continue
                match = _SHAPE_PATTERN.search(signal["reason"])
                if match is None:
                    raise AssertionError(signal)
                gini, share = map(float, match.groups())
                cached[index] = (
                    signal
                    if gini >= gini_min and share >= share_min
                    else _wait("Filtered by Gini sensitivity")
                )
            result = _summary_market(
                52.5,
                0.25,
                bars,
                start_index,
                cached,
            )
            print(
                json.dumps(
                    {
                        "months": args.months,
                        "gini": gini_min,
                        "share": share_min,
                        **result,
                    },
                    allow_nan=True,
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
