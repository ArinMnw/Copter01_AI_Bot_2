# -*- coding: utf-8 -*-
"""Compare fixed-TP vs ATR-trailing exit on a rollover strategy's own signals.

Replays the detector's signals (S206 by default) over one prepared price set and
scores each entry under several exit rules, so the exit is the only variable.

Example:
    python test_trailing_exit.py --strategy 206 --months 6
"""

from __future__ import annotations

import argparse
import importlib
import json
from datetime import datetime

from sim_strategy_backtest import BKK, parse_bkk, prepare_rates, validate_signal


def _equity_stats(profits):
    net = sum(profits)
    wins = sum(p > 0.0 for p in profits)
    gw = sum(p for p in profits if p > 0.0)
    gl = -sum(p for p in profits if p < 0.0)
    eq = pk = dd = 0.0
    for p in profits:
        eq += p
        pk = max(pk, eq)
        dd = max(dd, pk - eq)
    return {
        "trades": len(profits),
        "wins": wins,
        "win_rate": round(wins / len(profits) * 100.0, 1) if profits else None,
        "net": round(net, 2),
        "pf": round(gw / gl, 2) if gl else None,
        "max_dd": round(dd, 2),
    }


def _atr_at(bars, index, period=14):
    window = bars[max(0, index - period - 1):index]
    if len(window) < 2:
        return 0.0
    trs = []
    for i in range(1, len(window)):
        h, l, pc = window[i]["high"], window[i]["low"], window[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs) if trs else 0.0


def _simulate_exit(bars, fill_index, side, entry, sl, tp, mode, trail_mult, atr,
                   spread, lot):
    """Return realized pnl for one entry under the chosen exit rule."""
    active_sl = sl
    be_trigger = entry + side * abs(entry - sl)  # BE at 1R
    be_armed = False
    peak = entry
    for cursor in range(fill_index, len(bars)):
        low, high = float(bars[cursor]["low"]), float(bars[cursor]["high"])
        # SL first (conservative same-bar rule).
        if side > 0:
            if low <= active_sl:
                exit_price = active_sl
                break
            if mode == "fixed" and high >= tp:
                exit_price = tp
                break
            # trailing: ratchet stop up as price makes new highs
            if mode == "trail":
                peak = max(peak, high)
                trailed = peak - trail_mult * atr
                if trailed > active_sl:
                    active_sl = trailed
            if not be_armed and high >= be_trigger:
                be_armed = True
                active_sl = max(active_sl, entry)
        else:
            if high >= active_sl:
                exit_price = active_sl
                break
            if mode == "fixed" and low <= tp:
                exit_price = tp
                break
            if mode == "trail":
                peak = min(peak, low)
                trailed = peak + trail_mult * atr
                if trailed < active_sl:
                    active_sl = trailed
            if not be_armed and low <= be_trigger:
                be_armed = True
                active_sl = min(active_sl, entry)
    else:
        return None
    return float((side * (exit_price - entry) - spread) * 100.0 * lot)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", type=int, default=206)
    parser.add_argument("--months", type=int, default=6)
    parser.add_argument("--end", default="2026-07-18T00:00:00+07:00")
    parser.add_argument("--lookback", type=int, default=300)
    parser.add_argument("--spread", type=float, default=0.20)
    parser.add_argument("--lot", type=float, default=0.01)
    args = parser.parse_args()

    module = importlib.import_module(f"strategy{args.strategy}")
    detector = getattr(module, f"detect_s{args.strategy}")
    end = parse_bkk(args.end)
    bars, _, start_index = prepare_rates(args.months, "M5", end, args.lookback)

    entries = []
    next_free = start_index
    for index in range(start_index, len(bars) - 1):
        if index < next_free:
            continue
        window = bars[index - args.lookback + 1:index + 1]
        dt_bkk = datetime.fromtimestamp(int(bars[index]["time"]), tz=BKK)
        signal = detector(window, "M5", dt_bkk, {})
        validate_signal(signal, args.strategy)
        if signal["signal"] not in ("BUY", "SELL"):
            continue
        side = 1 if signal["signal"] == "BUY" else -1
        entry, sl, tp = float(signal["entry"]), float(signal["sl"]), float(signal["tp"])
        fill_index = index + 1  # market entry on next open (matches harness)
        atr = _atr_at(bars, index)
        entries.append((fill_index, side, entry, sl, tp, atr))
        # advance next_free past a nominal fixed-TP exit to avoid overlap bias
        next_free = fill_index + 1

    rules = [("fixed", None)]
    for m in (1.0, 1.5, 2.0, 2.5, 3.0):
        rules.append(("trail", m))

    for mode, mult in rules:
        profits = []
        last_exit = -1
        for fill_index, side, entry, sl, tp, atr in entries:
            if fill_index <= last_exit:
                continue
            pnl = _simulate_exit(bars, fill_index, side, entry, sl, tp, mode,
                                 mult or 0.0, atr, args.spread, args.lot)
            if pnl is None:
                continue
            profits.append(pnl)
        label = "fixed-10R" if mode == "fixed" else f"trail-{mult:g}ATR"
        print(json.dumps({"exit": label, **_equity_stats(profits)}))


if __name__ == "__main__":
    main()
