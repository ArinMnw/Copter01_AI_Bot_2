# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S401."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
    "latest": (2, "2026-07-30T00:00:00+07:00"),
}

GROUPS = {
    "buffer_local": (
        ("b014", {"SL_BUFFER_ATR": 0.14}),
        ("b015", {"SL_BUFFER_ATR": 0.15}),
        ("b016", {"SL_BUFFER_ATR": 0.16}),
        ("b017", {"SL_BUFFER_ATR": 0.17}),
        ("b018", {"SL_BUFFER_ATR": 0.18}),
        ("b019", {"SL_BUFFER_ATR": 0.19}),
        ("b020", {"SL_BUFFER_ATR": 0.20}),
    ),
    "ratio_local": (
        ("q105", {"QN_RATIO_MIN": 1.05}),
        ("q108", {"QN_RATIO_MIN": 1.08}),
        ("q110", {"QN_RATIO_MIN": 1.10}),
        ("q112", {"QN_RATIO_MIN": 1.12}),
        ("q114", {"QN_RATIO_MIN": 1.14}),
        ("q115", {"QN_RATIO_MIN": 1.15}),
    ),
    "focused": (
        ("base", {}),
        ("ratio100", {"QN_RATIO_MIN": 1.00}),
        ("ratio110", {"QN_RATIO_MIN": 1.10}),
        ("ratio120", {"QN_RATIO_MIN": 1.20}),
        ("recent020", {"BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("r020_q100", {"BASELINE_BARS": 60, "RECENT_BARS": 20,
                       "QN_RATIO_MIN": 1.00}),
        ("r020_q110", {"BASELINE_BARS": 60, "RECENT_BARS": 20,
                       "QN_RATIO_MIN": 1.10}),
        ("rise000", {"QN_RISE_ATR_MIN": 0.00}),
    ),
    "qn": (
        ("base", {}),
        ("ratio100", {"QN_RATIO_MIN": 1.00}),
        ("ratio130", {"QN_RATIO_MIN": 1.30}),
        ("ratio150", {"QN_RATIO_MIN": 1.50}),
        ("rise000", {"QN_RISE_ATR_MIN": 0.00}),
        ("rise060", {"QN_RISE_ATR_MIN": 0.06}),
        ("rise100", {"QN_RISE_ATR_MIN": 0.10}),
        ("baseline048", {"BASELINE_BARS": 48}),
        ("baseline096", {"BASELINE_BARS": 96}),
        ("recent020", {"BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("recent028", {"BASELINE_BARS": 84, "RECENT_BARS": 28}),
        ("recent032", {"BASELINE_BARS": 96, "RECENT_BARS": 32}),
    ),
    "payoff": (
        ("base", {}),
        ("buy_only", {"ALLOW_SELL": False}),
        ("sell_only", {"ALLOW_BUY": False}),
        ("rr8", {"TP_RR": 8.0}),
        ("rr9", {"TP_RR": 9.0}),
        ("rr10", {"TP_RR": 10.0}),
        ("rr11", {"TP_RR": 11.0}),
        ("be005", {"BE_RR": 0.05}),
        ("be010", {"BE_RR": 0.10}),
        ("buffer016", {"SL_BUFFER_ATR": 0.16}),
        ("buffer024", {"SL_BUFFER_ATR": 0.24}),
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
            401, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
