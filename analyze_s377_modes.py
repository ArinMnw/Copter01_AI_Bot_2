# -*- coding: utf-8 -*-
"""Split S377 outcomes by forecast mode and direction."""

from sim_strategy_backtest import backtest, parse_bkk


WINDOWS = (
    ("recent", 2, "2026-07-20T00:00:00+07:00"),
    ("h1", 6, "2026-07-01T00:00:00+07:00"),
    ("wf", 6, "2026-01-01T00:00:00+07:00"),
)


def _stats(trades):
    profits = [trade["profit"] for trade in trades]
    return {
        "closed": len(trades),
        "wins": sum(profit > 0.0 for profit in profits),
        "net": sum(profits),
    }


def main():
    for name, months, end_text in WINDOWS:
        _, trades = backtest(
            377,
            months,
            "M5",
            0.20,
            0.01,
            parse_bkk(end_text),
            300,
        )
        for mode in ("continuation", "reversal"):
            selected = [
                trade for trade in trades
                if trade["reason"].startswith(mode)
            ]
            print(name, mode, _stats(selected), flush=True)
        for direction in ("BUY", "SELL"):
            selected = [
                trade for trade in trades
                if trade["direction"] == direction
            ]
            print(name, direction, _stats(selected), flush=True)


if __name__ == "__main__":
    main()
