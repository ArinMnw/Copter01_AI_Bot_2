# -*- coding: utf-8 -*-
"""Cross-window robustness probes for S368."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
}

LOOSE = {
    "JUMP_RATIO_MIN": 3.0,
    "EVENT_RETURN_ATR_MIN": 0.50,
    "EVENT_RANGE_ATR_MIN": 1.00,
    "PRE_SHOCK_NET_ATR_MIN": 0.20,
    "PRE_SHOCK_PATH_EFFICIENCY_MIN": 0.08,
    "REJECTION_WICK_FRACTION_MIN": 0.15,
    "RECOVERY_FRACTION_MIN": 0.45,
    "MAX_RISK_ATR": 3.00,
}

GROUPS = {
    "breadth": (
        ("base", {}),
        ("loose", LOOSE),
        ("loose_jump4", {**LOOSE, "JUMP_RATIO_MIN": 4.0}),
        (
            "loose_wick10",
            {
                **LOOSE,
                "REJECTION_WICK_FRACTION_MIN": 0.10,
                "RECOVERY_FRACTION_MIN": 0.40,
            },
        ),
        (
            "loose_pre8",
            {**LOOSE, "PRE_SHOCK_BARS": 8},
        ),
        (
            "loose_pre_gate0",
            {
                **LOOSE,
                "PRE_SHOCK_NET_ATR_MIN": 0.0,
                "PRE_SHOCK_PATH_EFFICIENCY_MIN": 0.0,
            },
        ),
    ),
}


def _view(summary):
    return {
        key: summary[key]
        for key in (
            "closed",
            "wins",
            "win_rate",
            "net_profit",
            "profit_factor",
            "max_drawdown",
        )
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", choices=tuple(WINDOWS), required=True)
    parser.add_argument("--group", choices=tuple(GROUPS), required=True)
    args = parser.parse_args()
    months, end_text = WINDOWS[args.window]
    end = parse_bkk(end_text)
    prepared = prepare_rates(months, "M5", end, 300)
    for name, cfg in GROUPS[args.group]:
        summary, _ = backtest(
            368, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
