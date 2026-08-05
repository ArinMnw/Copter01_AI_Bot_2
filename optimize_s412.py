# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S412."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
    "latest": (2, "2026-07-30T00:00:00+07:00"),
}
GROUPS = {
    "structure": (
        ("base", {}),
        ("fade", {"FADE_PATH": True}),
        ("expand", {"EXPAND_OVERLAP": True}),
        ("expand_fade", {"EXPAND_OVERLAP": True, "FADE_PATH": True}),
        ("ratio070", {"OVERLAP_RATIO_MAX": 0.70}),
        ("ratio100", {"OVERLAP_RATIO_MAX": 1.00}),
        ("drop000", {"OVERLAP_DROP_MIN": 0.00}),
        ("drop008", {"OVERLAP_DROP_MIN": 0.08}),
        ("expand100", {"EXPAND_OVERLAP": True,
                       "OVERLAP_EXPANSION_RATIO_MIN": 1.00}),
        ("expand130", {"EXPAND_OVERLAP": True,
                       "OVERLAP_EXPANSION_RATIO_MIN": 1.30}),
        ("path006", {"PATH_EFFICIENCY_MIN": 0.06}),
        ("path020", {"PATH_EFFICIENCY_MIN": 0.20}),
        ("recent020", {"BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("recent028", {"BASELINE_BARS": 84, "RECENT_BARS": 28}),
        ("session0715", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15}),
        ("session1523", {"SESSION_START_HOUR": 15, "SESSION_END_HOUR": 23}),
    ),
    "finalists": (
        ("base", {}),
        ("drop008", {"OVERLAP_DROP_MIN": 0.08}),
        ("expand100", {"EXPAND_OVERLAP": True,
                       "OVERLAP_EXPANSION_RATIO_MIN": 1.00}),
        ("path020", {"PATH_EFFICIENCY_MIN": 0.20}),
        ("session0715", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15}),
        ("session0715_path020", {"SESSION_START_HOUR": 7,
                                 "SESSION_END_HOUR": 15,
                                 "PATH_EFFICIENCY_MIN": 0.20}),
    ),
    "direction": (
        ("base", {}),
        ("buy_only", {"ALLOW_SELL": False}),
        ("sell_only", {"ALLOW_BUY": False}),
        ("drop008_buy", {"OVERLAP_DROP_MIN": 0.08,
                         "ALLOW_SELL": False}),
        ("drop008_sell", {"OVERLAP_DROP_MIN": 0.08,
                          "ALLOW_BUY": False}),
    ),
}


def _view(summary):
    return {key: summary[key] for key in (
        "closed", "wins", "win_rate", "net_profit",
        "profit_factor", "max_drawdown",
    )}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", choices=tuple(WINDOWS), required=True)
    parser.add_argument("--group", choices=tuple(GROUPS), required=True)
    args = parser.parse_args()
    months, end_text = WINDOWS[args.window]
    end = parse_bkk(end_text)
    prepared = prepare_rates(months, "M5", end, 300)
    for name, cfg in GROUPS[args.group]:
        summary, _ = backtest(412, months, "M5", 0.20, 0.01, end, 300,
                              cfg, prepared)
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
