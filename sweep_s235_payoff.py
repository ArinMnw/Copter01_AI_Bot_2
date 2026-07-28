# -*- coding: utf-8 -*-
"""Fast exact payoff and breakeven sweep for S235."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import math

from sim_strategy_backtest import (
    BKK,
    backtest,
    parse_bkk,
    prepare_rates,
    validate_signal,
)
from strategy235 import detect_s235


RR_VALUES = tuple(round(28.0 + 0.1 * index, 1) for index in range(71))
BE_VALUES = tuple(round(0.80 + 0.01 * index, 2) for index in range(31))
CASES = tuple((rr, be) for rr in RR_VALUES for be in BE_VALUES) + ((10.0, 1.0),)


def _summary_market(
    rr, be_rr, bars, start_index, cached, spread=0.20, lot=0.01
):
    """Replay S235 with the generic backtester's market-fill semantics."""
    trades = []
    signals = invalid = 0
    next_free = start_index
    for index in range(start_index, len(bars) - 1):
        if index < next_free:
            continue
        signal = cached[index]
        if signal["signal"] not in ("BUY", "SELL"):
            continue
        signals += 1
        side = 1 if signal["signal"] == "BUY" else -1
        quoted_entry = float(signal["entry"])
        sl = float(signal["sl"])
        fill_index = index + 1
        entry = float(bars[fill_index]["open"])
        quoted_risk = side * (quoted_entry - sl)
        actual_risk = side * (entry - sl)
        if quoted_risk <= 0.0 or actual_risk <= 0.0:
            invalid += 1
            next_free = fill_index + 1
            continue
        raw_tp = quoted_entry + side * rr * quoted_risk
        tp = (
            math.ceil((raw_tp - 1e-12) * 100.0) / 100.0
            if side > 0
            else math.floor((raw_tp + 1e-12) * 100.0) / 100.0
        )
        be_trigger = entry + side * actual_risk * be_rr
        active_sl = sl
        be_armed = False
        outcome = exit_index = exit_price = None
        for cursor in range(fill_index, len(bars)):
            low = float(bars[cursor]["low"])
            high = float(bars[cursor]["high"])
            if side > 0:
                if low <= active_sl:
                    outcome, exit_price = ("BE" if be_armed else "SL"), active_sl
                elif high >= tp:
                    outcome, exit_price = "TP", tp
                elif high >= be_trigger:
                    be_armed, active_sl = True, entry
            else:
                if high >= active_sl:
                    outcome, exit_price = ("BE" if be_armed else "SL"), active_sl
                elif low <= tp:
                    outcome, exit_price = "TP", tp
                elif low <= be_trigger:
                    be_armed, active_sl = True, entry
            if outcome:
                exit_index = cursor
                break
        if outcome is None:
            break
        pnl = round(
            (side * (exit_price - entry) - spread) * (100.0 * lot), 2
        )
        trades.append((outcome, pnl))
        next_free = exit_index + 1

    profits = [pnl for _, pnl in trades]
    gross_profit = sum(max(0.0, pnl) for pnl in profits)
    gross_loss = -sum(min(0.0, pnl) for pnl in profits)
    equity = peak = max_dd = 0.0
    for pnl in profits:
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    wins = sum(outcome == "TP" for outcome, _ in trades)
    return {
        "rr": rr,
        "be": be_rr,
        "signals": signals,
        "closed": len(trades),
        "invalid": invalid,
        "wins": wins,
        "win_rate": 100.0 * wins / len(trades) if trades else 0.0,
        "net": sum(profits),
        "pf": gross_profit / gross_loss if gross_loss else math.inf,
        "max_dd": max_dd,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=2)
    args = parser.parse_args()
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    lookback = 300
    bars, start_bkk, start_index = prepare_rates(
        args.months, "M5", end, lookback
    )
    base_cfg = {"TP_RR": 10.0, "BE_RR": 1.0}
    cached = {}
    for index in range(start_index, len(bars) - 1):
        window = bars[index - lookback + 1:index + 1]
        dt_bkk = datetime.fromtimestamp(int(bars[index]["time"]), tz=BKK)
        signal = detect_s235(window, "M5", dt_bkk, base_cfg)
        validate_signal(signal, 235)
        cached[index] = signal
    rows = [
        _summary_market(rr, be, bars, start_index, cached)
        for rr, be in CASES
    ]
    official, _ = backtest(
        235,
        args.months,
        "M5",
        0.20,
        0.01,
        end,
        lookback,
        cfg=base_cfg,
        prepared=(bars, start_bkk, start_index),
    )
    base = next(row for row in rows if row["rr"] == 10.0 and row["be"] == 1.0)
    if (
        base["closed"] != official["closed"]
        or abs(base["net"] - official["net_profit"]) > 1e-7
    ):
        raise AssertionError({"cached_base": base, "official": official})
    rows.sort(key=lambda row: (row["net"], -row["max_dd"]), reverse=True)
    for row in rows:
        print(json.dumps(row, allow_nan=True), flush=True)


if __name__ == "__main__":
    main()
