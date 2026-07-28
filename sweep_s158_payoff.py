# -*- coding: utf-8 -*-
"""Fast exact payoff sweep for S158 by caching detector outputs once."""

from __future__ import annotations

import argparse
import json
import math

from datetime import datetime

from sim_strategy_backtest import (BKK, backtest, parse_bkk, prepare_rates,
                                   validate_signal)
from strategy158 import detect_s158


RRS = (7.0, 30.0, 40.0, 50.0, 60.0, 80.0, 100.0, 150.0, 200.0)


def _summary(rr, bars, start_index, cached, spread=0.20, lot=0.01):
    trades = []
    signals = expired = invalid = 0
    next_free = start_index
    for index in range(start_index, len(bars) - 1):
        if index < next_free:
            continue
        signal = cached[index]
        if signal["signal"] not in ("BUY", "SELL"):
            continue
        signals += 1
        side = 1 if signal["signal"] == "BUY" else -1
        entry = float(signal["entry"])
        sl = float(signal["sl"])
        pending_end = min(len(bars) - 1, index + int(signal["cancel_bars"] or 1))
        fill_index = None
        for pending_index in range(index + 1, pending_end + 1):
            low = float(bars[pending_index]["low"])
            high = float(bars[pending_index]["high"])
            if ((side > 0 and low <= entry - spread)
                    or (side < 0 and high >= entry + spread)):
                fill_index = pending_index
                break
        if fill_index is None:
            expired += 1
            next_free = pending_end + 1
            continue
        risk = side * (entry - sl)
        if risk <= 0.0:
            invalid += 1
            next_free = fill_index + 1
            continue
        raw_tp = entry + side * rr * risk
        tp = (math.ceil((raw_tp - 1e-12) * 100.0) / 100.0 if side > 0
              else math.floor((raw_tp + 1e-12) * 100.0) / 100.0)
        be_trigger = entry + side * risk * float(signal["be_rr"])
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
        pnl = (side * (exit_price - entry) - spread) * (100.0 * lot)
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
        "signals": signals,
        "closed": len(trades),
        "expired": expired,
        "invalid": invalid,
        "wins": wins,
        "win_rate": 100.0 * wins / len(trades) if trades else 0.0,
        "net": sum(profits),
        "pf": gross_profit / gross_loss if gross_loss else math.inf,
        "max_dd": max_dd,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=6)
    args = parser.parse_args()
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    lookback = 300
    bars, start_bkk, start_index = prepare_rates(args.months, "M5", end, lookback)
    cfg = {"CONFIRM_CLOSE_FRACTION": 0.80, "TP_RR": 7.0, "BE_RR": 1.0}
    cached = {}
    for index in range(start_index, len(bars) - 1):
        window = bars[index - lookback + 1:index + 1]
        dt_bkk = datetime.fromtimestamp(int(bars[index]["time"]), tz=BKK)
        signal = detect_s158(window, "M5", dt_bkk, cfg)
        validate_signal(signal, 158)
        cached[index] = signal
    rows = [_summary(rr, bars, start_index, cached) for rr in RRS]

    # Exactness guard against the authoritative runner at RR7.
    official, _ = backtest(158, args.months, "M5", 0.20, 0.01, end, lookback,
                           cfg=cfg, prepared=(bars, start_bkk, start_index))
    rr7 = rows[0]
    if (rr7["closed"] != official["closed"]
            or abs(rr7["net"] - official["net_profit"]) > 1e-7):
        raise AssertionError({"cached_rr7": rr7, "official_rr7": official})
    for row in rows:
        print(json.dumps(row, allow_nan=True), flush=True)


if __name__ == "__main__":
    main()
