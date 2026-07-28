# -*- coding: utf-8 -*-
"""Fast exact payoff and breakeven sweep for S199."""

from __future__ import annotations

import argparse
from datetime import datetime
import json

from sim_strategy_backtest import (BKK, backtest, parse_bkk, prepare_rates,
                                   validate_signal)
from strategy199 import detect_s199
from sweep_s161_payoff import _summary


CASES = tuple((rr, be)
              for rr in (7.0, 9.0, 11.0, 13.0, 16.9, 20.0, 25.0, 30.0)
              for be in (0.50, 0.75, 1.00, 1.25)) + ((7.0, 1.0),)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=6)
    parser.add_argument("--kurt-min", type=float, default=2.0)
    parser.add_argument("--kurt-window", type=int, default=96)
    parser.add_argument("--skip-guard", action="store_true")
    args = parser.parse_args()
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    lookback = 300
    bars, start_bkk, start_index = prepare_rates(args.months, "M5", end, lookback)
    base_cfg = {"KURT_MIN": args.kurt_min, "KURT_WINDOW": args.kurt_window,
                "TP_RR": 7.0, "BE_RR": 1.0}
    cached = {}
    for index in range(start_index, len(bars) - 1):
        window = bars[index - lookback + 1:index + 1]
        dt_bkk = datetime.fromtimestamp(int(bars[index]["time"]), tz=BKK)
        signal = detect_s199(window, "M5", dt_bkk, base_cfg)
        validate_signal(signal, 199)
        cached[index] = signal
    rows = [_summary(rr, be, bars, start_index, cached) for rr, be in CASES]

    if not args.skip_guard:
        official, _ = backtest(199, args.months, "M5", 0.20, 0.01, end, lookback,
                               cfg=base_cfg,
                               prepared=(bars, start_bkk, start_index))
        rr7 = next(row for row in rows if row["rr"] == 7.0 and row["be"] == 1.0)
        if (rr7["closed"] != official["closed"]
                or abs(rr7["net"] - official["net_profit"]) > 1e-7):
            raise AssertionError({"cached_rr7": rr7, "official_rr7": official})
    rows.sort(key=lambda row: (row["net"], -row["max_dd"]), reverse=True)
    for row in rows:
        print(json.dumps(row, allow_nan=True), flush=True)


if __name__ == "__main__":
    main()
