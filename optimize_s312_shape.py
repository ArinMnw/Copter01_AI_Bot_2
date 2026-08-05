# -*- coding: utf-8 -*-
"""Cross-window release-candle shape audit for optimized S312 SELL."""

from __future__ import annotations

import argparse
from datetime import datetime
import json

from sim_strategy_backtest import BKK, backtest, parse_bkk, prepare_rates, validate_signal
from strategy119 import _atr, _bars
from strategy312 import detect_s312
from sweep_s235_payoff import _summary_market


PERIODS = (
    ("recent", 2, "2026-07-20T00:00:00+07:00"),
    ("h1", 6, "2026-07-20T00:00:00+07:00"),
    ("wf", 6, "2026-01-20T00:00:00+07:00"),
)
BODY_VALUES = (0.40, 0.50, 0.575, 0.65, 0.75)
RANGE_VALUES = (0.80, 1.00, 1.20)
CLOSE_VALUES = (0.70, 0.80, 0.8325, 0.90)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--body-values")
    parser.add_argument("--range-values")
    parser.add_argument("--close-values")
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()
    body_values = (
        tuple(float(value) for value in args.body_values.split(","))
        if args.body_values
        else BODY_VALUES
    )
    range_values = (
        tuple(float(value) for value in args.range_values.split(","))
        if args.range_values
        else RANGE_VALUES
    )
    close_values = (
        tuple(float(value) for value in args.close_values.split(","))
        if args.close_values
        else CLOSE_VALUES
    )
    permissive_cfg = {
        "ENERGY_MIN": 0.225,
        "ALLOW_BUY": False,
        "ALLOW_SELL": True,
        "RELEASE_BODY_ATR_MIN": 0.0,
        "RELEASE_RANGE_ATR_MIN": 0.0,
        "RELEASE_CLOSE_FRACTION": 0.0,
        "TP_RR": 10.1,
        "BE_RR": 0.075,
    }
    prepared = {}
    cached = {}
    geometry = {}
    for name, months, end_text in PERIODS:
        end = parse_bkk(end_text)
        bars, start_bkk, start_index = prepare_rates(months, "M5", end, 300)
        prepared[name] = (months, end, bars, start_bkk, start_index)
        period_cache = {}
        period_geometry = {}
        for index in range(start_index, len(bars) - 1):
            window = bars[index - 299:index + 1]
            dt_bkk = datetime.fromtimestamp(int(bars[index]["time"]), tz=BKK)
            signal = detect_s312(window, "M5", dt_bkk, permissive_cfg)
            validate_signal(signal, 312)
            period_cache[index] = signal
            if signal.get("signal") == "SELL":
                normalized = _bars(window)
                atr = _atr(normalized[:-1], 14)
                event = normalized[-1]
                event_range = event["high"] - event["low"]
                period_geometry[index] = (
                    abs(event["close"] - event["open"]) / atr,
                    event_range / atr,
                    (event["high"] - event["close"]) / event_range,
                )
            else:
                period_geometry[index] = None
        cached[name] = period_cache
        geometry[name] = period_geometry

    rows = []
    for body_min in body_values:
        for range_min in range_values:
            for close_min in close_values:
                result = {
                    "body": body_min,
                    "range": range_min,
                    "close": close_min,
                }
                nets = []
                dds = []
                viable = True
                for name, _, _ in PERIODS:
                    _, _, bars, _, start_index = prepared[name]
                    filtered = {
                        index: (
                            signal
                            if geometry[name][index] is not None
                            and geometry[name][index][0] + 1e-12 >= body_min
                            and geometry[name][index][1] + 1e-12 >= range_min
                            and geometry[name][index][2] + 1e-12 >= close_min
                            else {"signal": "WAIT", "reason": "Below shape gate"}
                        )
                        for index, signal in cached[name].items()
                    }
                    summary = _summary_market(
                        10.1,
                        0.075,
                        bars,
                        start_index,
                        filtered,
                        spread=0.20,
                        lot=0.01,
                    )
                    result[name] = summary
                    nets.append(summary["net"])
                    dds.append(summary["max_dd"])
                    viable = viable and summary["wins"] > 0 and summary["net"] > 0.0
                result["viable"] = viable
                result["net_sum"] = sum(nets)
                result["worst_net"] = min(nets)
                result["worst_dd"] = max(dds)
                result["net_dd"] = (
                    result["net_sum"] / result["worst_dd"]
                    if result["worst_dd"] > 0.0
                    else float("inf")
                )
                rows.append(result)

    base = next(
        (
            row for row in rows
            if row["body"] == 0.575
            and row["range"] == 1.00
            and row["close"] == 0.8325
        ),
        None,
    )
    if base is None:
        base = {"body": 0.575, "range": 1.00, "close": 0.8325}
        for name, _, _ in PERIODS:
            _, _, bars, _, start_index = prepared[name]
            filtered = {
                index: (
                    signal
                    if geometry[name][index] is not None
                    and geometry[name][index][0] + 1e-12 >= 0.575
                    and geometry[name][index][1] + 1e-12 >= 1.00
                    and geometry[name][index][2] + 1e-12 >= 0.8325
                    else {"signal": "WAIT", "reason": "Below base shape gate"}
                )
                for index, signal in cached[name].items()
            }
            base[name] = _summary_market(
                10.1,
                0.075,
                bars,
                start_index,
                filtered,
                spread=0.20,
                lot=0.01,
            )
    exact_cfg = {
        "ENERGY_MIN": 0.225,
        "ALLOW_BUY": False,
        "ALLOW_SELL": True,
        "TP_RR": 10.1,
        "BE_RR": 0.075,
    }
    for name, months, _ in PERIODS:
        _, end, bars, start_bkk, start_index = prepared[name]
        official, _ = backtest(
            312,
            months,
            "M5",
            0.20,
            0.01,
            end,
            300,
            cfg=exact_cfg,
            prepared=(bars, start_bkk, start_index),
        )
        if (
            base[name]["closed"] != official["closed"]
            or abs(base[name]["net"] - official["net_profit"]) > 1e-7
        ):
            raise AssertionError({
                "period": name,
                "cached": base[name],
                "official": official,
            })

    viable_rows = [row for row in rows if row["viable"]]
    viable_rows.sort(
        key=lambda row: (
            row["net_dd"],
            row["worst_net"],
            row["net_sum"],
        ),
        reverse=True,
    )
    for row in viable_rows[:max(1, args.top)]:
        print(json.dumps(row, allow_nan=True), flush=True)
    print(json.dumps({"parity": "ok", "base": base}, allow_nan=True))


if __name__ == "__main__":
    main()
