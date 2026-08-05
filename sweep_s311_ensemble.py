# -*- coding: utf-8 -*-
"""Cached CvM-threshold sweep for the S311 multi-window ensemble."""

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
from strategy311 import detect_s311
from sweep_s235_payoff import _summary_market


def _cvm_from_signal(signal):
    if signal.get("signal") not in ("BUY", "SELL"):
        return None
    marker = "CvM="
    reason = str(signal.get("reason", ""))
    try:
        return float(reason.split(marker, 1)[1].split(",", 1)[0])
    except (IndexError, ValueError):
        raise AssertionError(f"S311 signal has no parseable CvM: {reason!r}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--windows", default="14,16,18")
    parser.add_argument("--thresholds", default="0.20,0.22,0.23,0.24,0.25,0.26,0.28")
    args = parser.parse_args()

    windows = tuple(int(value) for value in args.windows.split(","))
    thresholds = tuple(float(value) for value in args.thresholds.split(","))
    end = parse_bkk(args.end)
    bars, start_bkk, start_index = prepare_rates(args.months, "M5", end, 300)
    permissive_cfg = {
        "RECENT_RETURNS_ENSEMBLE": windows,
        "CVM_MIN": 0.0,
    }
    permissive = {}
    cvm_by_index = {}
    for index in range(start_index, len(bars) - 1):
        window = bars[index - 299:index + 1]
        dt_bkk = datetime.fromtimestamp(int(bars[index]["time"]), tz=BKK)
        signal = detect_s311(window, "M5", dt_bkk, permissive_cfg)
        validate_signal(signal, 311)
        permissive[index] = signal
        cvm_by_index[index] = _cvm_from_signal(signal)

    for threshold in thresholds:
        cached = {
            index: (
                signal
                if cvm_by_index[index] is not None
                and cvm_by_index[index] + 5e-7 >= threshold
                else {"signal": "WAIT", "reason": "Below swept CvM threshold"}
            )
            for index, signal in permissive.items()
        }
        row = _summary_market(
            10.1, 0.25, bars, start_index, cached, spread=0.20, lot=0.01
        )
        row.update({
            "months": args.months,
            "end": end.isoformat(),
            "windows": windows,
            "cvm_min": threshold,
        })
        print(json.dumps(row, allow_nan=True), flush=True)

    # Prove cached filtering is identical to the authoritative detector/replay
    # for one interior threshold on every requested period.
    parity_threshold = 0.24
    parity_cached = {
        index: (
            signal
            if cvm_by_index[index] is not None
            and cvm_by_index[index] + 5e-7 >= parity_threshold
            else {"signal": "WAIT", "reason": "Below parity CvM threshold"}
        )
        for index, signal in permissive.items()
    }
    cached_summary = _summary_market(
        10.1, 0.25, bars, start_index, parity_cached, spread=0.20, lot=0.01
    )
    official, _ = backtest(
        311,
        args.months,
        "M5",
        0.20,
        0.01,
        end,
        300,
        cfg={
            "RECENT_RETURNS_ENSEMBLE": windows,
            "CVM_MIN": parity_threshold,
        },
        prepared=(bars, start_bkk, start_index),
    )
    if (
        cached_summary["closed"] != official["closed"]
        or abs(cached_summary["net"] - official["net_profit"]) > 1e-7
    ):
        raise AssertionError({
            "cached": cached_summary,
            "official": official,
        })
    print(json.dumps({"parity": "ok", "official": official}, allow_nan=True))


if __name__ == "__main__":
    main()
