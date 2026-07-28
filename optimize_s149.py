# -*- coding: utf-8 -*-
"""Reproducible S149 parameter grid on one shared MT5 dataset."""

from __future__ import annotations

import argparse
import itertools
import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


def _values(text, fallback=None):
    return [float(value) for value in text.split(",")] if text else [fallback]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--end", default="2026-07-18T00:00:00+07:00")
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument("--rr", default="7,8,10,12")
    parser.add_argument("--be", default="0.75,1.0,1.25")
    parser.add_argument("--range-q", default="")
    parser.add_argument("--volume-q", default="")
    parser.add_argument("--wick-min", default="")
    parser.add_argument("--entry-fraction", default="")
    parser.add_argument("--sl-buffer", default="")
    args = parser.parse_args()
    end = parse_bkk(args.end)
    prepared = prepare_rates(args.months, "M5", end, 300)
    axes = (_values(args.rr), _values(args.be), _values(args.range_q),
            _values(args.volume_q), _values(args.wick_min),
            _values(args.entry_fraction), _values(args.sl_buffer))
    rows = []
    for rr, be, range_q, volume_q, wick_min, entry_fraction, sl_buffer in itertools.product(*axes):
        cfg = {"TP_RR": rr, "BE_RR": be}
        for key, value in (("RANGE_QUANTILE", range_q),
                           ("VOLUME_QUANTILE", volume_q),
                           ("WICK_MIN_FRACTION", wick_min),
                           ("WICK_ENTRY_FRACTION", entry_fraction),
                           ("SL_EXTREME_BUFFER_ATR", sl_buffer)):
            if value is not None:
                cfg[key] = value
        summary, _ = backtest(149, args.months, "M5", 0.20, 0.01, end, 300,
                              cfg=cfg, prepared=prepared)
        rows.append({
            "rr": rr, "be": be, "range_q": range_q, "volume_q": volume_q,
            "wick_min": wick_min, "entry_fraction": entry_fraction,
            "sl_buffer": sl_buffer, "signals": summary["signals"],
            "closed": summary["closed"], "wins": summary["wins"],
            "win_rate": summary["win_rate"], "net": summary["net_profit"],
            "pf": summary["profit_factor"], "max_dd": summary["max_drawdown"],
        })
    rows.sort(key=lambda row: (row["net"], -row["max_dd"]), reverse=True)
    for row in rows:
        print(json.dumps(row, allow_nan=True))


if __name__ == "__main__":
    main()
