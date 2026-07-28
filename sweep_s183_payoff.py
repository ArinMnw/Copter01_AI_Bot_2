# -*- coding: utf-8 -*-
"""Fast exact payoff and breakeven sweep for S183."""

from __future__ import annotations

import argparse
from datetime import datetime
import json

from sim_strategy_backtest import (BKK, backtest, parse_bkk, prepare_rates,
                                   validate_signal)
from strategy183 import detect_s183
from sweep_s161_payoff import _summary


CASES = tuple((rr, be)
              for rr in (10.0, 10.1, 10.2, 10.3, 10.4)
              for be in (0.85, 0.88, 0.90, 0.92, 0.95)) + ((7.0, 1.0),)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument("--skip-guard", action="store_true")
    args = parser.parse_args()
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    lookback = 300
    bars, start_bkk, start_index = prepare_rates(args.months, "M5", end, lookback)
    base_cfg = {"TP_RR": 7.0, "BE_RR": 1.0}
    cached = {}
    for index in range(start_index, len(bars) - 1):
        window = bars[index - lookback + 1:index + 1]
        dt_bkk = datetime.fromtimestamp(int(bars[index]["time"]), tz=BKK)
        signal = detect_s183(window, "M5", dt_bkk, base_cfg)
        validate_signal(signal, 183)
        cached[index] = signal
    rows = [_summary(rr, be, bars, start_index, cached) for rr, be in CASES]

    if not args.skip_guard:
        official, _ = backtest(183, args.months, "M5", 0.20, 0.01, end, lookback,
                               cfg=base_cfg, prepared=(bars, start_bkk, start_index))
        rr7 = next(row for row in rows if row["rr"] == 7.0 and row["be"] == 1.0)
        if (rr7["closed"] != official["closed"]
                or abs(rr7["net"] - official["net_profit"]) > 1e-7):
            raise AssertionError({"cached_rr7": rr7, "official_rr7": official})
    rows.sort(key=lambda row: (row["net"], -row["max_dd"]), reverse=True)
    for row in rows:
        print(json.dumps(row, allow_nan=True), flush=True)


if __name__ == "__main__":
    main()
