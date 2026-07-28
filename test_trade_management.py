# -*- coding: utf-8 -*-
"""Compare trade-management schemes on a strategy's own signals.

Entries are held fixed (the detector's own signals, same fills as the standard
harness) so the management scheme is the only variable. Schemes:

  fixed     - the strategy's own TP/BE (baseline)
  scaleout  - close a fraction at `partial_r`, move the rest to breakeven
  pyramid   - add a second unit at `add_r`, its stop at the original entry
  timestop  - flatten at market if not at +1R after `time_bars` bars

Example:
    python test_trade_management.py --strategy 206 --months 6
"""

from __future__ import annotations

import argparse
import importlib
import json
from datetime import datetime

from sim_strategy_backtest import BKK, parse_bkk, prepare_rates, validate_signal


def _stats(profits):
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
        "win_rate": round(wins / len(profits) * 100.0, 1) if profits else None,
        "net": round(net, 2),
        "pf": round(gw / gl, 2) if gl else None,
        "max_dd": round(dd, 2),
        "ratio": round(net / dd, 1) if dd > 0 else None,
    }


def _run(bars, fill_index, side, entry, sl, tp, risk, scheme, args, spread, lot):
    """Simulate one entry under one management scheme; return realized pnl."""
    unit = 100.0 * lot
    be_level = entry + side * risk * args.be_r
    partial_level = entry + side * risk * args.partial_r
    add_level = entry + side * risk * args.add_r

    active_sl = sl
    be_armed = False
    booked = 0.0            # pnl already realized from partial closes
    open_frac = 1.0         # fraction of the original unit still open
    added = False
    add_entry = None
    add_sl = None

    for cursor in range(fill_index, len(bars)):
        low, high = float(bars[cursor]["low"]), float(bars[cursor]["high"])
        # Conservative: stops checked before targets within the same bar.
        hit_sl = low <= active_sl if side > 0 else high >= active_sl
        if hit_sl:
            booked += (side * (active_sl - entry) - spread) * unit * open_frac
            if added:
                booked += (side * (active_sl - add_entry) - spread) * unit * args.add_frac
            return booked
        if added:
            hit_add_sl = low <= add_sl if side > 0 else high >= add_sl
            if hit_add_sl:
                booked += (side * (add_sl - add_entry) - spread) * unit * args.add_frac
                added = False

        hit_tp = high >= tp if side > 0 else low <= tp
        if hit_tp:
            booked += (side * (tp - entry) - spread) * unit * open_frac
            if added:
                booked += (side * (tp - add_entry) - spread) * unit * args.add_frac
            return booked

        reached = high if side > 0 else low
        progress = side * (reached - entry)

        if scheme == "scaleout" and open_frac == 1.0 and progress >= side * side * risk * args.partial_r:
            if (side > 0 and high >= partial_level) or (side < 0 and low <= partial_level):
                booked += (side * (partial_level - entry) - spread) * unit * args.partial_frac
                open_frac = 1.0 - args.partial_frac
                active_sl = entry          # rest rides risk-free
                be_armed = True
        if scheme == "pyramid" and not added and open_frac > 0.0:
            if (side > 0 and high >= add_level) or (side < 0 and low <= add_level):
                added = True
                add_entry = add_level
                add_sl = entry
        if scheme == "timestop" and cursor - fill_index >= args.time_bars:
            if progress < risk:
                exit_price = float(bars[cursor]["close"])
                booked += (side * (exit_price - entry) - spread) * unit * open_frac
                if added:
                    booked += (side * (exit_price - add_entry) - spread) * unit * args.add_frac
                return booked
        if not be_armed and args.be_r > 0.0:
            if (side > 0 and high >= be_level) or (side < 0 and low <= be_level):
                be_armed = True
                active_sl = entry if side > 0 else entry
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", type=int, default=206)
    parser.add_argument("--months", type=int, default=6)
    parser.add_argument("--end", default="2026-07-18T00:00:00+07:00")
    parser.add_argument("--lookback", type=int, default=320)
    parser.add_argument("--spread", type=float, default=0.20)
    parser.add_argument("--lot", type=float, default=0.01)
    parser.add_argument("--be-r", type=float, default=1.0)
    parser.add_argument("--partial-r", type=float, default=3.0)
    parser.add_argument("--partial-frac", type=float, default=0.5)
    parser.add_argument("--add-r", type=float, default=3.0)
    parser.add_argument("--add-frac", type=float, default=1.0)
    parser.add_argument("--time-bars", type=int, default=24)
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
        entry = float(signal["entry"])
        sl, tp = float(signal["sl"]), float(signal["tp"])
        risk = side * (entry - sl)
        if risk <= 0:
            continue
        entries.append((index + 1, side, entry, sl, tp, risk))
        next_free = index + 2

    for scheme in ("fixed", "scaleout", "pyramid", "timestop"):
        profits = []
        for fill_index, side, entry, sl, tp, risk in entries:
            pnl = _run(bars, fill_index, side, entry, sl, tp, risk, scheme,
                       args, args.spread, args.lot)
            if pnl is not None:
                profits.append(float(pnl))
        print(json.dumps({"scheme": scheme, **_stats(profits)}), flush=True)


if __name__ == "__main__":
    main()
