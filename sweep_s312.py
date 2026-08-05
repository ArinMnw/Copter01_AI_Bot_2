# -*- coding: utf-8 -*-
"""Cached direction/energy-threshold audit for S312."""

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
from strategy312 import detect_s312
from sweep_s235_payoff import _summary_market


def _energy_from_signal(signal):
    if signal.get("signal") not in ("BUY", "SELL"):
        return None
    reason = str(signal.get("reason", ""))
    try:
        return float(reason.split("Energy distance=", 1)[1].split(",", 1)[0])
    except (IndexError, ValueError):
        raise AssertionError(f"S312 signal has no parseable energy: {reason!r}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument(
        "--thresholds",
        default="0,0.10,0.15,0.20,0.25,0.30,0.40,0.50,0.60",
    )
    args = parser.parse_args()

    thresholds = tuple(float(value) for value in args.thresholds.split(","))
    end = parse_bkk(args.end)
    bars, start_bkk, start_index = prepare_rates(args.months, "M5", end, 300)
    permissive_cfg = {
        "ENERGY_MIN": 0.0,
        "ALLOW_BUY": True,
        "ALLOW_SELL": True,
    }
    permissive = {}
    energy_by_index = {}
    for index in range(start_index, len(bars) - 1):
        window = bars[index - 299:index + 1]
        dt_bkk = datetime.fromtimestamp(int(bars[index]["time"]), tz=BKK)
        signal = detect_s312(window, "M5", dt_bkk, permissive_cfg)
        validate_signal(signal, 312)
        permissive[index] = signal
        energy_by_index[index] = _energy_from_signal(signal)

    directions = {
        "both": {"BUY", "SELL"},
        "buy": {"BUY"},
        "sell": {"SELL"},
    }
    for threshold in thresholds:
        for direction_name, allowed in directions.items():
            cached = {
                index: (
                    signal
                    if energy_by_index[index] is not None
                    and energy_by_index[index] + 5e-7 >= threshold
                    and signal.get("signal") in allowed
                    else {"signal": "WAIT", "reason": "Below swept S312 gate"}
                )
                for index, signal in permissive.items()
            }
            row = _summary_market(
                10.0, 0.25, bars, start_index, cached, spread=0.20, lot=0.01
            )
            row.update({
                "months": args.months,
                "end": end.isoformat(),
                "energy_min": threshold,
                "direction": direction_name,
            })
            print(json.dumps(row, allow_nan=True), flush=True)

    parity_cached = {
        index: (
            signal
            if energy_by_index[index] is not None
            and energy_by_index[index] + 5e-7 >= 0.20
            else {"signal": "WAIT", "reason": "Below parity energy threshold"}
        )
        for index, signal in permissive.items()
    }
    cached_summary = _summary_market(
        10.0, 0.25, bars, start_index, parity_cached, spread=0.20, lot=0.01
    )
    official, _ = backtest(
        312,
        args.months,
        "M5",
        0.20,
        0.01,
        end,
        300,
        cfg={"ENERGY_MIN": 0.20},
        prepared=(bars, start_bkk, start_index),
    )
    if (
        cached_summary["closed"] != official["closed"]
        or abs(cached_summary["net"] - official["net_profit"]) > 1e-7
    ):
        raise AssertionError({"cached": cached_summary, "official": official})
    print(json.dumps({"parity": "ok", "official": official}, allow_nan=True))


if __name__ == "__main__":
    main()
