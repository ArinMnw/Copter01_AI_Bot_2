# -*- coding: utf-8 -*-
"""Walk-forward robustness matrix for the optimized S135 candidates."""

from __future__ import annotations

import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


CANDIDATES = {
    "strict": {"MAX_RISK_ATR": 2.5, "RV_EXPANSION_MIN": 2.15,
               "PREVIOUS_RV_MAX": 0.8},
    "moderate": {"MAX_RISK_ATR": 2.5, "RV_EXPANSION_MIN": 2.0,
                 "PREVIOUS_RV_MAX": 1.0},
    "broad": {"MAX_RISK_ATR": 2.5, "RV_EXPANSION_MIN": 1.55,
              "PREVIOUS_RV_MAX": 1.0},
}
WINDOW_ENDS = (
    "2026-03-17T00:00:00+07:00",
    "2026-05-17T00:00:00+07:00",
    "2026-07-17T00:00:00+07:00",
)


def main():
    for end_text in WINDOW_ENDS:
        end = parse_bkk(end_text)
        prepared = prepare_rates(2, "M5", end, 300)
        for name, source in CANDIDATES.items():
            cfg = {"TP_RR": 14.0, "BE_RR": 1.0,
                   "SOURCE_CFG": {"S120_CFG": source}}
            summary, _ = backtest(135, 2, "M5", 0.20, 0.01, end, 300,
                                  cfg=cfg, prepared=prepared)
            print(json.dumps({
                "window_end": end_text[:10], "candidate": name,
                "closed": summary["closed"], "wins": summary["wins"],
                "win_rate": summary["win_rate"], "net": summary["net_profit"],
                "pf": summary["profit_factor"], "max_dd": summary["max_drawdown"],
            }, allow_nan=True))


if __name__ == "__main__":
    main()
