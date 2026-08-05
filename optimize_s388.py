# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S388."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
    "latest": (2, "2026-07-30T00:00:00+07:00"),
}

GROUPS = {
    "duration": (
        ("base", {}),
        ("mean000", {"RUN_MEAN_RISE_MIN": 0.00}),
        ("mean025", {"RUN_MEAN_RISE_MIN": 0.25}),
        ("mean075", {"RUN_MEAN_RISE_MIN": 0.75}),
        ("mean100", {"RUN_MEAN_RISE_MIN": 1.00}),
        ("share035", {"LONG_RUN_EVENT_SHARE_MIN": 0.35}),
        ("share065", {"LONG_RUN_EVENT_SHARE_MIN": 0.65}),
        ("longest2", {"MIN_LONGEST_RUN": 2}),
        ("longest4", {"MIN_LONGEST_RUN": 4}),
        ("q055", {"TAIL_QUANTILE": 0.55}),
        ("q065", {"TAIL_QUANTILE": 0.65}),
        ("direction025", {"TAIL_DIRECTIONAL_VOLUME_MIN": 0.25}),
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
        ("baseline060", {"BASELINE_BARS": 60}),
        ("baseline100", {"BASELINE_BARS": 100}),
        ("recent020", {"RECENT_BARS": 20}),
        ("recent028", {"RECENT_BARS": 28}),
        ("events3", {"MIN_TAIL_EVENTS": 3}),
        ("events5", {"MIN_TAIL_EVENTS": 5}),
        ("body055", {"EVENT_BODY_ATR_MIN": 0.55}),
        ("body075", {"EVENT_BODY_ATR_MIN": 0.75}),
        ("fraction072", {"EVENT_BODY_FRACTION_MIN": 0.72}),
        ("fraction078", {"EVENT_BODY_FRACTION_MIN": 0.78}),
    ),
    "narrow": (
        ("base", {}),
        ("mean100", {"RUN_MEAN_RISE_MIN": 1.00}),
        ("direction025", {"TAIL_DIRECTIONAL_VOLUME_MIN": 0.25}),
        ("mean100_direction025", {"RUN_MEAN_RISE_MIN": 1.00, "TAIL_DIRECTIONAL_VOLUME_MIN": 0.25}),
    ),
    "focused": (
        ("core", {"RUN_MEAN_RISE_MIN": 1.00}),
        ("buy_only", {"RUN_MEAN_RISE_MIN": 1.00, "ALLOW_SELL": False}),
        ("sell_only", {"RUN_MEAN_RISE_MIN": 1.00, "ALLOW_BUY": False}),
        ("rr8", {"RUN_MEAN_RISE_MIN": 1.00, "TP_RR": 8.0}),
        ("rr9", {"RUN_MEAN_RISE_MIN": 1.00, "TP_RR": 9.0}),
        ("rr10", {"RUN_MEAN_RISE_MIN": 1.00, "TP_RR": 10.0}),
        ("be005", {"RUN_MEAN_RISE_MIN": 1.00, "BE_RR": 0.05}),
    ),
    "final": (
        ("rr10", {"RUN_MEAN_RISE_MIN": 1.00, "TP_RR": 10.0}),
        ("rr11", {"RUN_MEAN_RISE_MIN": 1.00, "TP_RR": 11.0}),
        ("rr12", {"RUN_MEAN_RISE_MIN": 1.00, "TP_RR": 12.0}),
        ("rr14", {"RUN_MEAN_RISE_MIN": 1.00, "TP_RR": 14.0}),
        ("sell_rr10", {"RUN_MEAN_RISE_MIN": 1.00, "TP_RR": 10.0, "ALLOW_BUY": False}),
        ("rr10_mean125", {"RUN_MEAN_RISE_MIN": 1.25, "TP_RR": 10.0}),
        ("rr10_mean150", {"RUN_MEAN_RISE_MIN": 1.50, "TP_RR": 10.0}),
        ("rr10_share065", {"RUN_MEAN_RISE_MIN": 1.00, "TP_RR": 10.0, "LONG_RUN_EVENT_SHARE_MIN": 0.65}),
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
            388, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
