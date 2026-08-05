# -*- coding: utf-8 -*-
"""Final reproducible cross-window, spread, and payload audit for S409."""

from datetime import datetime

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates
from strategy409 import detect_s409


WINDOWS = (
    ("recent", 2, "2026-07-20T00:00:00+07:00"),
    ("h1", 6, "2026-07-01T00:00:00+07:00"),
    ("wf", 6, "2026-01-01T00:00:00+07:00"),
    ("latest", 2, "2026-07-30T00:00:00+07:00"),
)
SUMMARY_KEYS = (
    "signals", "closed", "wins", "win_rate", "net_profit",
    "pnl_per_day", "pnl_per_month", "profit_factor", "max_drawdown",
)


def main():
    for name, months, end_text in WINDOWS:
        end = parse_bkk(end_text)
        prepared = prepare_rates(months, "M5", end, 300)
        for spread in (0.20, 0.50):
            summary, trades = backtest(409, months, "M5", spread, 0.01,
                                       end, 300, prepared=prepared)
            print(name, spread,
                  {key: summary[key] for key in SUMMARY_KEYS}, flush=True)
            if spread == 0.20 and name == "h1" and trades:
                target = datetime.fromisoformat(trades[-1]["signal_time"])
                bars = prepared[0]
                for index, bar in enumerate(bars):
                    if int(bar["time"]) == int(target.timestamp()):
                        print("payload_smoke", detect_s409(
                            bars[index - 299:index + 1], "M5", target, {}
                        ), flush=True)
                        break


if __name__ == "__main__":
    main()
