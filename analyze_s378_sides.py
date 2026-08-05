# -*- coding: utf-8 -*-
"""Split S378 baseline outcomes by direction."""

from sim_strategy_backtest import backtest, parse_bkk


WINDOWS = (
    ("recent", 2, "2026-07-20T00:00:00+07:00"),
    ("h1", 6, "2026-07-01T00:00:00+07:00"),
    ("wf", 6, "2026-01-01T00:00:00+07:00"),
)


def main():
    for name, months, end_text in WINDOWS:
        _, trades = backtest(
            378,
            months,
            "M5",
            0.20,
            0.01,
            parse_bkk(end_text),
            300,
        )
        for direction in ("BUY", "SELL"):
            selected = [
                trade for trade in trades
                if trade["direction"] == direction
            ]
            profits = [trade["profit"] for trade in selected]
            print(
                name,
                direction,
                {
                    "closed": len(selected),
                    "wins": sum(profit > 0.0 for profit in profits),
                    "net": sum(profits),
                },
                flush=True,
            )


if __name__ == "__main__":
    main()
