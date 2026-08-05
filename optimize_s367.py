# -*- coding: utf-8 -*-
"""Cross-window robustness probes for S367."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
}

GROUPS = {
    "payoff": (
        ("base", {}),
        ("buy_only", {"ALLOW_SELL": False}),
        ("sell_only", {"ALLOW_BUY": False}),
        ("rr7", {"TP_RR": 7.0}),
        ("rr9", {"TP_RR": 9.0}),
        ("rr10", {"TP_RR": 10.0}),
        ("be001", {"BE_RR": 0.01}),
        ("be002", {"BE_RR": 0.02}),
        ("be005", {"BE_RR": 0.05}),
        ("be012", {"BE_RR": 0.12}),
    ),
    "shape": (
        ("base", {}),
        ("entropy_max086", {"ENTROPY_MAX": 0.86}),
        ("entropy_max088", {"ENTROPY_MAX": 0.88}),
        ("entropy_max092", {"ENTROPY_MAX": 0.92}),
        ("drop003", {"ENTROPY_DROP_MIN": 0.03}),
        ("drop007", {"ENTROPY_DROP_MIN": 0.07}),
        ("drop009", {"ENTROPY_DROP_MIN": 0.09}),
        ("mono005", {"MONOTONE_IMBALANCE_MIN": 0.05}),
        ("mono012", {"MONOTONE_IMBALANCE_MIN": 0.12}),
        ("mono016", {"MONOTONE_IMBALANCE_MIN": 0.16}),
        ("path014", {"PATH_EFFICIENCY_MIN": 0.14}),
        ("path022", {"PATH_EFFICIENCY_MIN": 0.22}),
        ("path026", {"PATH_EFFICIENCY_MIN": 0.26}),
        ("body060", {"RELEASE_BODY_ATR_MIN": 0.60}),
        ("body080", {"RELEASE_BODY_ATR_MIN": 0.80}),
        ("body090", {"RELEASE_BODY_ATR_MIN": 0.90}),
    ),
    "payoff_combo": (
        ("rr7_be001", {"TP_RR": 7.0, "BE_RR": 0.01}),
        ("rr7_be002", {"TP_RR": 7.0, "BE_RR": 0.02}),
        ("rr8_be001", {"TP_RR": 8.0, "BE_RR": 0.01}),
        ("rr8_be002", {"TP_RR": 8.0, "BE_RR": 0.02}),
        ("rr9_be001", {"TP_RR": 9.0, "BE_RR": 0.01}),
        ("rr9_be002", {"TP_RR": 9.0, "BE_RR": 0.02}),
        ("rr10_be001", {"TP_RR": 10.0, "BE_RR": 0.01}),
        ("rr10_be002", {"TP_RR": 10.0, "BE_RR": 0.02}),
    ),
    "shape_combo": (
        ("drop007", {"ENTROPY_DROP_MIN": 0.07}),
        (
            "drop007_entropy088",
            {"ENTROPY_DROP_MIN": 0.07, "ENTROPY_MAX": 0.88},
        ),
        (
            "drop007_mono012",
            {"ENTROPY_DROP_MIN": 0.07, "MONOTONE_IMBALANCE_MIN": 0.12},
        ),
        (
            "drop007_path022",
            {"ENTROPY_DROP_MIN": 0.07, "PATH_EFFICIENCY_MIN": 0.22},
        ),
        (
            "drop007_body080",
            {"ENTROPY_DROP_MIN": 0.07, "RELEASE_BODY_ATR_MIN": 0.80},
        ),
    ),
    "windows": (
        ("base", {}),
        ("baseline060", {"BASELINE_BARS": 60}),
        ("baseline100", {"BASELINE_BARS": 100}),
        ("baseline120", {"BASELINE_BARS": 120}),
        ("recent016", {"RECENT_BARS": 16}),
        ("recent024", {"RECENT_BARS": 24}),
        ("net040", {"NET_MOVE_ATR_MIN": 0.40}),
        ("net060", {"NET_MOVE_ATR_MIN": 0.60}),
        ("close075", {"RELEASE_CLOSE_FRACTION": 0.75}),
        ("close085", {"RELEASE_CLOSE_FRACTION": 0.85}),
    ),
    "close_local": (
        ("close070", {"RELEASE_CLOSE_FRACTION": 0.70}),
        ("close074", {"RELEASE_CLOSE_FRACTION": 0.74}),
        ("close075", {"RELEASE_CLOSE_FRACTION": 0.75}),
        ("close076", {"RELEASE_CLOSE_FRACTION": 0.76}),
        ("close078", {"RELEASE_CLOSE_FRACTION": 0.78}),
        ("close080", {"RELEASE_CLOSE_FRACTION": 0.80}),
        ("close082", {"RELEASE_CLOSE_FRACTION": 0.82}),
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
    optimized_payoff = (
        {}
        if args.group in ("payoff", "payoff_combo")
        else {"TP_RR": 7.0, "BE_RR": 0.02}
    )
    if args.group in ("windows", "close_local"):
        optimized_payoff["ENTROPY_DROP_MIN"] = 0.07
        optimized_payoff["ENTROPY_MAX"] = 0.88
    for name, override in GROUPS[args.group]:
        cfg = {**optimized_payoff, **override}
        summary, _ = backtest(
            367, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
