# -*- coding: utf-8 -*-
"""Cross-window robustness probes for S372."""

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
        ("rr7_be001", {"TP_RR": 7.0, "BE_RR": 0.01}),
        ("rr9_be001", {"TP_RR": 9.0, "BE_RR": 0.01}),
    ),
    "shape": (
        ("base", {}),
        ("kurt250", {"KURTOSIS_MIN": 2.50}),
        ("kurt350", {"KURTOSIS_MIN": 3.50}),
        ("kurt450", {"KURTOSIS_MIN": 4.50}),
        ("ratio105", {"KURTOSIS_RATIO_MIN": 1.05}),
        ("ratio125", {"KURTOSIS_RATIO_MIN": 1.25}),
        ("ratio140", {"KURTOSIS_RATIO_MIN": 1.40}),
        ("tail015", {"DIRECTIONAL_TAIL_MIN": 0.15}),
        ("tail035", {"DIRECTIONAL_TAIL_MIN": 0.35}),
        ("tail050", {"DIRECTIONAL_TAIL_MIN": 0.50}),
        ("path014", {"PATH_EFFICIENCY_MIN": 0.14}),
        ("path022", {"PATH_EFFICIENCY_MIN": 0.22}),
        ("body060", {"RELEASE_BODY_ATR_MIN": 0.60}),
        ("body080", {"RELEASE_BODY_ATR_MIN": 0.80}),
        ("close075", {"RELEASE_CLOSE_FRACTION": 0.75}),
        ("close085", {"RELEASE_CLOSE_FRACTION": 0.85}),
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
    ),
    "interaction": (
        ("base", {}),
        ("path022", {"PATH_EFFICIENCY_MIN": 0.22}),
        ("body060", {"RELEASE_BODY_ATR_MIN": 0.60}),
        (
            "path022_body060",
            {
                "PATH_EFFICIENCY_MIN": 0.22,
                "RELEASE_BODY_ATR_MIN": 0.60,
            },
        ),
        (
            "path022_body060_tail050",
            {
                "PATH_EFFICIENCY_MIN": 0.22,
                "RELEASE_BODY_ATR_MIN": 0.60,
                "DIRECTIONAL_TAIL_MIN": 0.50,
            },
        ),
        (
            "path022_body060_ratio105",
            {
                "PATH_EFFICIENCY_MIN": 0.22,
                "RELEASE_BODY_ATR_MIN": 0.60,
                "KURTOSIS_RATIO_MIN": 1.05,
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
            372, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
