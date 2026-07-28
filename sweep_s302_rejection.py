# -*- coding: utf-8 -*-
"""Cached rejection-geometry sensitivity for S302 SELL signals."""

from __future__ import annotations

import argparse
from datetime import datetime
import json

from sim_strategy_backtest import BKK, parse_bkk, prepare_rates, validate_signal
from strategy119 import _atr, _bars
from strategy197 import _wait
from strategy302 import detect_s302
from sweep_s235_payoff import _summary_market


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument("--body-values", default="0.25,0.35,0.40,0.50,0.60")
    parser.add_argument("--range-values", default="0.60,0.70,0.80,0.90,1.00")
    parser.add_argument("--close-values", default="0.55,0.60,0.62,0.65,0.70")
    parser.add_argument("--wick-values", default="0.05,0.10,0.15,0.20,0.25")
    args = parser.parse_args()
    body_values = tuple(float(value) for value in args.body_values.split(","))
    range_values = tuple(float(value) for value in args.range_values.split(","))
    close_values = tuple(float(value) for value in args.close_values.split(","))
    wick_values = tuple(float(value) for value in args.wick_values.split(","))
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
                "KS_SCALED_MIN": 0.975,
                "MEDIAN_SHIFT_MAD_MIN": 0.02,
                "REJECTION_BODY_ATR_MIN": 0.0,
                "REJECTION_RANGE_ATR_MIN": 0.0,
                "REJECTION_CLOSE_FRACTION": 0.0,
                "DRIFT_SIDE_WICK_FRACTION_MIN": 0.0,
                "TP_RR": 26.3,
                "BE_RR": 0.95,
            },
        )
        validate_signal(signal, 302)
        if signal["signal"] in ("BUY", "SELL"):
            normalized = _bars(window)
            atr = _atr(normalized[:-1], 14)
            event = normalized[-1]
            event_range = event["high"] - event["low"]
            metrics = (
                abs(event["close"] - event["open"]) / atr,
                event_range / atr,
                (event["high"] - event["close"]) / event_range,
                (
                    event["high"] - max(event["open"], event["close"])
                ) / event_range,
            )
        else:
            metrics = None
        raw[index] = (signal, metrics)
    for body_min in body_values:
        for range_min in range_values:
            for close_min in close_values:
                for wick_min in wick_values:
                    cached = {}
                    for index, (signal, metrics) in raw.items():
                        if metrics is None:
                            cached[index] = signal
                            continue
                        body, event_range, close, wick = metrics
                        cached[index] = (
                            signal
                            if (
                                body >= body_min
                                and event_range >= range_min
                                and close >= close_min
                                and wick >= wick_min
                            )
                            else _wait("Filtered by S302 rejection sensitivity")
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
                                "body": body_min,
                                "range": range_min,
                                "close": close_min,
                                "wick": wick_min,
                                **result,
                            },
                            allow_nan=True,
                        ),
                        flush=True,
                    )


if __name__ == "__main__":
    main()
