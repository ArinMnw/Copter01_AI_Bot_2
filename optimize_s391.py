# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S391."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
    "latest": (2, "2026-07-30T00:00:00+07:00"),
}

GROUPS = {
    "exhaustion": (
        ("base", {}),
        ("negative010", {"NEGATIVE_PARTIAL_MIN": 0.10}),
        ("negative015", {"NEGATIVE_PARTIAL_MIN": 0.15}),
        ("negative025", {"NEGATIVE_PARTIAL_MIN": 0.25}),
        ("negative030", {"NEGATIVE_PARTIAL_MIN": 0.30}),
        ("drop005", {"PARTIAL_DROP_MIN": 0.05}),
        ("drop010", {"PARTIAL_DROP_MIN": 0.10}),
        ("drop020", {"PARTIAL_DROP_MIN": 0.20}),
        ("drop025", {"PARTIAL_DROP_MIN": 0.25}),
        ("raw010", {"LEAD_CORR_MIN": 0.10}),
        ("baseline060", {"BASELINE_BARS": 60}),
        ("baseline100", {"BASELINE_BARS": 100}),
        ("recent020", {"RECENT_BARS": 20}),
        ("recent028", {"RECENT_BARS": 28}),
    ),
    "payoff": (
        ("base", {}),
        ("buy_only", {"ALLOW_SELL": False}),
        ("sell_only", {"ALLOW_BUY": False}),
        ("rr8", {"TP_RR": 8.0}),
        ("rr9", {"TP_RR": 9.0}),
        ("rr10", {"TP_RR": 10.0}),
        ("be001", {"BE_RR": 0.01}),
        ("be005", {"BE_RR": 0.05}),
        ("be010", {"BE_RR": 0.10}),
    ),
    "breadth": (
        ("base", {}),
        ("flow005", {"DIRECTIONAL_FLOW_MIN": 0.05}),
        ("flow020", {"DIRECTIONAL_FLOW_MIN": 0.20}),
        ("path010", {"PATH_EFFICIENCY_MIN": 0.10}),
        ("path025", {"PATH_EFFICIENCY_MIN": 0.25}),
        ("body055", {"EVENT_BODY_ATR_MIN": 0.55}),
        ("body075", {"EVENT_BODY_ATR_MIN": 0.75}),
        ("fraction068", {"EVENT_BODY_FRACTION_MIN": 0.68}),
        ("fraction078", {"EVENT_BODY_FRACTION_MIN": 0.78}),
    ),
    "narrow": (
        ("base", {}),
        ("negative010", {"NEGATIVE_PARTIAL_MIN": 0.10}),
        ("negative030", {"NEGATIVE_PARTIAL_MIN": 0.30}),
        ("drop025", {"PARTIAL_DROP_MIN": 0.25}),
        ("recent020", {"RECENT_BARS": 20}),
    ),
}


def _view(summary):
    return {
        key: summary[key]
        for key in (
            "closed", "wins", "win_rate", "net_profit",
            "profit_factor", "max_drawdown",
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
            391, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
