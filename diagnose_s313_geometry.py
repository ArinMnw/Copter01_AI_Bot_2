# -*- coding: utf-8 -*-
"""Print closed-candle geometry for S313 optimization trades."""

import csv
from datetime import datetime

from sim_strategy_backtest import parse_bkk, prepare_rates
from strategy119 import _atr, _bars


SOURCES = (
    ("s313_6m.csv", 6, "2026-07-20T00:00:00+07:00"),
    ("s313_wf.csv", 6, "2026-01-20T00:00:00+07:00"),
)


def main():
    seen = set()
    for csv_path, months, end_text in SOURCES:
        end = parse_bkk(end_text)
        rates, _, _ = prepare_rates(months, "M5", end, 300)
        by_time = {int(bar["time"]): index for index, bar in enumerate(rates)}
        with open(csv_path, encoding="utf-8", newline="") as handle:
            for trade in csv.DictReader(handle):
                signal_time = trade["signal_time"]
                if signal_time in seen:
                    continue
                seen.add(signal_time)
                timestamp = int(datetime.fromisoformat(signal_time).timestamp())
                index = by_time[timestamp]
                bars = _bars(rates[index - 299:index + 1])
                event = bars[-1]
                atr = _atr(bars[:-1], 14)
                candle_range = event["high"] - event["low"]
                close_fraction = (event["high"] - event["close"]) / candle_range
                print(
                    signal_time,
                    trade["outcome"],
                    f"body={abs(event['close'] - event['open']) / atr:.4f}",
                    f"range={candle_range / atr:.4f}",
                    f"close={close_fraction:.4f}",
                )


if __name__ == "__main__":
    main()
