# -*- coding: utf-8 -*-
"""Six-month robustness validation for bounded S158 candidates."""

from __future__ import annotations

import json

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


CASES = (
    ("default", {}),
    ("jump_3.5", {"JUMP_SIGMA_MIN": 3.50}),
    ("volume_q90", {"JUMP_VOLUME_QUANTILE": 0.90}),
    ("confirm_80", {"CONFIRM_CLOSE_FRACTION": 0.80}),
    ("confirm_60", {"CONFIRM_CLOSE_FRACTION": 0.60}),
)


def main():
    months = 6
    end = parse_bkk("2026-07-18T00:00:00+07:00")
    prepared = prepare_rates(months, "M5", end, 300)
    for name, cfg in CASES:
        summary, _ = backtest(158, months, "M5", 0.20, 0.01, end, 300,
                              cfg=cfg, prepared=prepared)
        print(json.dumps({
            "case": name,
            "cfg": cfg,
            "signals": summary["signals"],
            "closed": summary["closed"],
            "wins": summary["wins"],
            "win_rate": summary["win_rate"],
            "net": summary["net_profit"],
            "pf": summary["profit_factor"],
            "max_dd": summary["max_drawdown"],
        }, allow_nan=True, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
