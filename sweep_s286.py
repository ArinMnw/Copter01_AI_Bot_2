# -*- coding: utf-8 -*-
"""Exact cached threshold/payoff sweep for S286."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import re

from sim_strategy_backtest import (
    BKK,
    backtest,
    parse_bkk,
    prepare_rates,
    validate_signal,
)
from strategy286 import detect_s286
from sweep_s235_payoff import _summary_market


Z_VALUES = tuple(round(0.50 + 0.25 * index, 2) for index in range(17))
RR_VALUES = tuple(round(7.0 + 0.5 * index, 1) for index in range(67))
BE_VALUES = tuple(round(0.20 + 0.05 * index, 2) for index in range(27))
FINE_RR_VALUES = tuple(round(26.50 + 0.10 * index, 2) for index in range(11))
FINE_BE_VALUES = tuple(round(0.20 + 0.02 * index, 2) for index in range(141))
_Z_RE = re.compile(r"\(z=(-?\d+(?:\.\d+)?)\)")


def _cache_candidates(bars, start_index, lookback, sweep_lookback):
    cfg = {
        "ALLOW_BUY": False,
        "ALLOW_SELL": True,
        "MK_Z_MIN_ABS": 0.0,
        "SWEEP_LOOKBACK": sweep_lookback,
        "TP_RR": 10.0,
        "BE_RR": 1.0,
    }
    cached = {}
    zscores = {}
    for index in range(start_index, len(bars) - 1):
        window = bars[index - lookback + 1:index + 1]
        dt_bkk = datetime.fromtimestamp(int(bars[index]["time"]), tz=BKK)
        signal = detect_s286(window, "M5", dt_bkk, cfg)
        validate_signal(signal, 286)
        cached[index] = signal
        if signal.get("signal") in ("BUY", "SELL"):
            match = _Z_RE.search(signal["reason"])
            if not match:
                raise AssertionError(signal["reason"])
            zscores[index] = abs(float(match.group(1)))
    return cached, zscores


def _filtered(cached, zscores, z_min):
    return {
        index: (
            signal
            if index in zscores and zscores[index] >= z_min
            else {"signal": "WAIT", "reason": "Below swept MK threshold"}
        )
        for index, signal in cached.items()
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument(
        "--stage",
        choices=("threshold", "payoff", "fine"),
        default="threshold",
    )
    parser.add_argument("--z", type=float, default=2.0)
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--sweep-lookback", type=int, default=14)
    args = parser.parse_args()
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    lookback = 300
    bars, start_bkk, start_index = prepare_rates(
        args.months, "M5", end, lookback
    )
    cached, zscores = _cache_candidates(
        bars, start_index, lookback, args.sweep_lookback
    )

    if args.stage == "threshold":
        rows = []
        for z_min in Z_VALUES:
            row = _summary_market(
                10.0,
                1.0,
                bars,
                start_index,
                _filtered(cached, zscores, z_min),
            )
            row["z"] = z_min
            rows.append(row)
        official, _ = backtest(
            286,
            args.months,
            "M5",
            0.20,
            0.01,
            end,
            lookback,
            cfg={
                "ALLOW_BUY": False,
                "ALLOW_SELL": True,
                "MK_Z_MIN_ABS": 2.0,
                "SWEEP_LOOKBACK": args.sweep_lookback,
                "TP_RR": 10.0,
                "BE_RR": 1.0,
            },
            prepared=(bars, start_bkk, start_index),
        )
        base = next(row for row in rows if row["z"] == 2.0)
        if (
            base["closed"] != official["closed"]
            or abs(base["net"] - official["net_profit"]) > 1e-7
        ):
            raise AssertionError({"cached_base": base, "official": official})
        for row in rows:
            print(json.dumps(row, allow_nan=True), flush=True)
        return

    selected = _filtered(cached, zscores, args.z)
    if args.probe:
        rr_values = (27.0, 27.1)
        be_values = (1.48, 1.50, 1.52, 1.59, 1.68, 1.70)
    else:
        rr_values = FINE_RR_VALUES if args.stage == "fine" else RR_VALUES
        be_values = FINE_BE_VALUES if args.stage == "fine" else BE_VALUES
    rows = [
        {
            **_summary_market(rr, be, bars, start_index, selected),
            "z": args.z,
        }
        for rr in rr_values
        for be in be_values
    ]
    if args.probe:
        rows.sort(key=lambda row: (row["rr"], row["be"]))
        for row in rows:
            print(json.dumps(row, allow_nan=True), flush=True)
        return
    rows.sort(
        key=lambda row: (row["net"], row["wins"], -row["max_dd"]),
        reverse=True,
    )
    for row in rows[:max(1, args.top)]:
        print(json.dumps(row, allow_nan=True), flush=True)


if __name__ == "__main__":
    main()
