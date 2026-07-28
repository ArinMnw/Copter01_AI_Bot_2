# -*- coding: utf-8 -*-
"""Reproducible S140 grid using one shared MT5 price dataset."""

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
    parser.add_argument("--rr", default="7,8,10,12,14")
    parser.add_argument("--be", default="0.75,1.0,1.25")
    parser.add_argument("--max-risk-atr", default="")
    parser.add_argument("--max-risk-price-pct", default="")
    parser.add_argument("--sl-buffer-atr", default="")
    parser.add_argument("--rv-min", default="")
    parser.add_argument("--previous-rv-max", default="")
    parser.add_argument("--efficiency-min", default="")
    args = parser.parse_args()
    end = parse_bkk(args.end)
    prepared = prepare_rates(args.months, "M5", end, 300)
    axes = (
        _values(args.rr), _values(args.be), _values(args.max_risk_atr),
        _values(args.max_risk_price_pct), _values(args.sl_buffer_atr), _values(args.rv_min),
        _values(args.previous_rv_max), _values(args.efficiency_min),
    )
    rows = []
    for rr, be, max_risk, max_risk_pct, sl_buffer, rv_min, previous_max, efficiency in itertools.product(*axes):
        cfg = {"TP_RR": rr, "BE_RR": be}
        if max_risk is not None:
            cfg["MAX_SHORT_RISK_ATR"] = max_risk
        if max_risk_pct is not None:
            cfg["MAX_RISK_PRICE_PCT"] = max_risk_pct
        if sl_buffer is not None:
            cfg["SL_SIGNAL_BUFFER_ATR"] = sl_buffer
        source = {}
        if rv_min is not None:
            source["RV_EXPANSION_MIN"] = rv_min
        if previous_max is not None:
            source["PREVIOUS_RV_MAX"] = previous_max
        if efficiency is not None:
            source["EFFICIENCY_MIN"] = efficiency
        if source:
            cfg["SOURCE_CFG"] = source
        summary, _ = backtest(140, args.months, "M5", 0.20, 0.01, end, 300,
                              cfg=cfg, prepared=prepared)
        rows.append({
            "rr": rr, "be": be, "max_risk_atr": max_risk,
            "max_risk_price_pct": max_risk_pct,
            "sl_buffer_atr": sl_buffer, "rv_min": rv_min,
            "previous_rv_max": previous_max, "efficiency_min": efficiency,
            "signals": summary["signals"], "closed": summary["closed"],
            "wins": summary["wins"], "win_rate": summary["win_rate"],
            "net": summary["net_profit"], "pf": summary["profit_factor"],
            "max_dd": summary["max_drawdown"],
        })
    rows.sort(key=lambda row: (row["net"], -row["max_dd"]), reverse=True)
    for row in rows:
        print(json.dumps(row, allow_nan=True))


if __name__ == "__main__":
    main()
