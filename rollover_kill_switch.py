# -*- coding: utf-8 -*-
"""Live regime health check for the rollover champions (S206 / S218 / S202).

Operationalizes the kill-switch prescribed in rollover_champions.md: the rollover
drive edge only works in "drive" epochs (breakouts continue) and dies in "fade"
epochs (breakouts revert). This computes the same causal continuation-rate that
S218 uses as its gate, plus the champions' own recent realized P&L, and emits a
GO / CAUTION / PAUSE recommendation. Meant to be run daily (e.g. after rollover).

Example:
    python rollover_kill_switch.py
    python rollover_kill_switch.py --since 2026-07-01
"""

from __future__ import annotations

import argparse
import json

from sim_strategy_backtest import BKK, backtest, parse_bkk, prepare_rates
from strategy119 import _atr, _bars
from strategy218 import _continuation_rate, DEFAULT_CFG as S218_CFG


def _regime_rate(months=1, lookback=700):
    """Current market continuation-rate (S218's regime measure), causal to now."""
    end = parse_bkk(None)
    bars_raw, _, start_index = prepare_rates(months, "M5", end, lookback)
    bars = _bars(bars_raw)
    atr = _atr(bars[:-1], int(S218_CFG["ATR_PERIOD"]))
    if atr <= 0.0:
        return None, 0
    return _continuation_rate(bars, atr, S218_CFG)


def _recent_pnl(strategy_id, since, months=2):
    end = parse_bkk(None)
    summary, trades = backtest(strategy_id, months, "M5", 0.20, 0.01, end, 320)
    recent = [t for t in trades if parse_bkk(t["signal_time"]) >= since]
    net = sum(t["profit"] for t in recent)
    eq = pk = dd = 0.0
    for t in recent:
        eq += t["profit"]
        pk = max(pk, eq)
        dd = max(dd, pk - eq)
    return {"trades": len(recent), "net": round(net, 2), "max_dd": round(dd, 2)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", help="BKK date YYYY-MM-DD for recent P&L window")
    parser.add_argument("--strategies", default="206,202")
    parser.add_argument("--drive-floor", type=float, default=0.50,
                        help="continuation-rate below this = fade regime = PAUSE")
    parser.add_argument("--caution-floor", type=float, default=0.55,
                        help="between this and drive-floor = CAUTION")
    # DD alarm from the S206 MC study: p99 maxDD ~ $88 on 0.01 lot / 12m of trades.
    parser.add_argument("--dd-alarm", type=float, default=90.0)
    args = parser.parse_args()

    since = parse_bkk((args.since or "2026-01-01") + "T00:00:00+07:00")
    rate, events = _regime_rate()

    if rate is None or events < int(S218_CFG["REGIME_MIN_EVENTS"]):
        regime = "UNKNOWN"
    elif rate >= args.caution_floor:
        regime = "DRIVE"
    elif rate >= args.drive_floor:
        regime = "CAUTION"
    else:
        regime = "FADE"

    pnl = {sid: _recent_pnl(int(sid), since)
           for sid in args.strategies.split(",")}
    dd_breach = any(p["max_dd"] > args.dd_alarm for p in pnl.values())

    if regime == "FADE" or dd_breach:
        recommendation = "PAUSE"
    elif regime in ("CAUTION", "UNKNOWN"):
        recommendation = "CAUTION"
    else:
        recommendation = "GO"

    print(json.dumps({
        "regime": regime,
        "continuation_rate": round(rate, 3) if rate is not None else None,
        "regime_events": events,
        "recent_pnl": pnl,
        "dd_breach": dd_breach,
        "recommendation": recommendation,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
