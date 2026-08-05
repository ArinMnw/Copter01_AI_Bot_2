# -*- coding: utf-8 -*-
"""Cross-window exact payoff/BE optimization for S312 SELL signals."""

from __future__ import annotations

import argparse
from datetime import datetime
import json

from sim_strategy_backtest import BKK, backtest, parse_bkk, prepare_rates, validate_signal
from strategy312 import detect_s312
from sweep_s235_payoff import _summary_market


PERIODS = (
    ("recent", 2, "2026-07-20T00:00:00+07:00"),
    ("h1", 6, "2026-07-20T00:00:00+07:00"),
    ("wf", 6, "2026-01-20T00:00:00+07:00"),
)
RR_VALUES = tuple(round(7.0 + 0.25 * index, 2) for index in range(53))
BE_VALUES = tuple(round(0.15 + 0.05 * index, 2) for index in range(18))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rr-values")
    parser.add_argument("--be-values")
    parser.add_argument("--top", type=int, default=40)
    args = parser.parse_args()
    rr_values = (
        tuple(float(value) for value in args.rr_values.split(","))
        if args.rr_values
        else RR_VALUES
    )
    be_values = (
        tuple(float(value) for value in args.be_values.split(","))
        if args.be_values
        else BE_VALUES
    )
    detector_cfg = {
        "ENERGY_MIN": 0.225,
        "ALLOW_BUY": False,
        "ALLOW_SELL": True,
    }
    prepared = {}
    cached = {}
    for name, months, end_text in PERIODS:
        end = parse_bkk(end_text)
        bars, start_bkk, start_index = prepare_rates(months, "M5", end, 300)
        prepared[name] = (months, end, bars, start_bkk, start_index)
        period_cache = {}
        for index in range(start_index, len(bars) - 1):
            window = bars[index - 299:index + 1]
            dt_bkk = datetime.fromtimestamp(int(bars[index]["time"]), tz=BKK)
            signal = detect_s312(window, "M5", dt_bkk, detector_cfg)
            validate_signal(signal, 312)
            period_cache[index] = signal
        cached[name] = period_cache

    rows = []
    for rr in rr_values:
        for be_rr in be_values:
            result = {"rr": rr, "be": be_rr}
            nets = []
            dds = []
            viable = True
            for name, _, _ in PERIODS:
                _, _, bars, _, start_index = prepared[name]
                summary = _summary_market(
                    rr,
                    be_rr,
                    bars,
                    start_index,
                    cached[name],
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

    # Exact parity at the current payoff before considering optimization.
    base = next(
        (
            row for row in rows
            if row["rr"] == 10.0 and row["be"] == 0.25
        ),
        None,
    )
    if base is None:
        base = {"rr": 10.0, "be": 0.25}
        for name, _, _ in PERIODS:
            _, _, bars, _, start_index = prepared[name]
            base[name] = _summary_market(
                10.0,
                0.25,
                bars,
                start_index,
                cached[name],
                spread=0.20,
                lot=0.01,
            )
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
            cfg=detector_cfg,
            prepared=(bars, start_bkk, start_index),
        )
        cached_base = base[name]
        if (
            cached_base["closed"] != official["closed"]
            or abs(cached_base["net"] - official["net_profit"]) > 1e-7
        ):
            raise AssertionError({
                "period": name,
                "cached": cached_base,
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
