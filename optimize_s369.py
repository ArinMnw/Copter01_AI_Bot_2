# -*- coding: utf-8 -*-
"""Cross-window robustness probes for S369."""

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
        ("control015", {"CONTROL_MIN": 0.15}),
        ("control025", {"CONTROL_MIN": 0.25}),
        ("control030", {"CONTROL_MIN": 0.30}),
        ("ratio110", {"CONTROL_RATIO_MIN": 1.10}),
        ("ratio130", {"CONTROL_RATIO_MIN": 1.30}),
        ("ratio150", {"CONTROL_RATIO_MIN": 1.50}),
        ("path014", {"PATH_EFFICIENCY_MIN": 0.14}),
        ("path022", {"PATH_EFFICIENCY_MIN": 0.22}),
        ("body060", {"RELEASE_BODY_ATR_MIN": 0.60}),
        ("body080", {"RELEASE_BODY_ATR_MIN": 0.80}),
        ("close075", {"RELEASE_CLOSE_FRACTION": 0.75}),
        ("close085", {"RELEASE_CLOSE_FRACTION": 0.85}),
    ),
    "shape_core": (
        ("base", {}),
        ("control015", {"CONTROL_MIN": 0.15}),
        ("control025", {"CONTROL_MIN": 0.25}),
        ("control030", {"CONTROL_MIN": 0.30}),
        ("path022", {"PATH_EFFICIENCY_MIN": 0.22}),
        ("body080", {"RELEASE_BODY_ATR_MIN": 0.80}),
        ("close075", {"RELEASE_CLOSE_FRACTION": 0.75}),
    ),
    "shape_final": (
        ("base", {}),
        ("control030", {"CONTROL_MIN": 0.30}),
        ("path022", {"PATH_EFFICIENCY_MIN": 0.22}),
        ("body080", {"RELEASE_BODY_ATR_MIN": 0.80}),
        ("close075", {"RELEASE_CLOSE_FRACTION": 0.75}),
    ),
    "shape_combo": (
        ("path022", {"PATH_EFFICIENCY_MIN": 0.22}),
        (
            "path022_body080",
            {
                "PATH_EFFICIENCY_MIN": 0.22,
                "RELEASE_BODY_ATR_MIN": 0.80,
            },
        ),
        (
            "path022_control025",
            {
                "PATH_EFFICIENCY_MIN": 0.22,
                "CONTROL_MIN": 0.25,
            },
        ),
    ),
    "body_cliff": (
        (
            "body080",
            {
                "PATH_EFFICIENCY_MIN": 0.22,
                "RELEASE_BODY_ATR_MIN": 0.80,
            },
        ),
        (
            "body084",
            {
                "PATH_EFFICIENCY_MIN": 0.22,
                "RELEASE_BODY_ATR_MIN": 0.84,
            },
        ),
        (
            "body088",
            {
                "PATH_EFFICIENCY_MIN": 0.22,
                "RELEASE_BODY_ATR_MIN": 0.88,
            },
        ),
        (
            "body090",
            {
                "PATH_EFFICIENCY_MIN": 0.22,
                "RELEASE_BODY_ATR_MIN": 0.90,
            },
        ),
    ),
    "payoff_local": (
        ("rr8_be001", {"TP_RR": 8.0, "BE_RR": 0.01}),
        ("rr9_be001", {"TP_RR": 9.0, "BE_RR": 0.01}),
        ("rr10_be001", {"TP_RR": 10.0, "BE_RR": 0.01}),
        ("rr11_be001", {"TP_RR": 11.0, "BE_RR": 0.01}),
        ("rr12_be001", {"TP_RR": 12.0, "BE_RR": 0.01}),
    ),
    "payoff_high": (
        ("rr12_be001", {"TP_RR": 12.0, "BE_RR": 0.01}),
        ("rr14_be001", {"TP_RR": 14.0, "BE_RR": 0.01}),
        ("rr16_be001", {"TP_RR": 16.0, "BE_RR": 0.01}),
        ("rr18_be001", {"TP_RR": 18.0, "BE_RR": 0.01}),
        ("rr20_be001", {"TP_RR": 20.0, "BE_RR": 0.01}),
    ),
    "payoff_ultra": (
        ("rr20_be001", {"TP_RR": 20.0, "BE_RR": 0.01}),
        ("rr24_be001", {"TP_RR": 24.0, "BE_RR": 0.01}),
        ("rr28_be001", {"TP_RR": 28.0, "BE_RR": 0.01}),
        ("rr32_be001", {"TP_RR": 32.0, "BE_RR": 0.01}),
        ("rr36_be001", {"TP_RR": 36.0, "BE_RR": 0.01}),
        ("rr40_be001", {"TP_RR": 40.0, "BE_RR": 0.01}),
    ),
    "payoff_cliff": (
        ("rr24_be001", {"TP_RR": 24.0, "BE_RR": 0.01}),
        ("rr25_be001", {"TP_RR": 25.0, "BE_RR": 0.01}),
        ("rr26_be001", {"TP_RR": 26.0, "BE_RR": 0.01}),
        ("rr27_be001", {"TP_RR": 27.0, "BE_RR": 0.01}),
        ("rr28_be001", {"TP_RR": 28.0, "BE_RR": 0.01}),
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
    parser.add_argument("--probe")
    args = parser.parse_args()
    months, end_text = WINDOWS[args.window]
    end = parse_bkk(end_text)
    prepared = prepare_rates(months, "M5", end, 300)
    optimized_payoff = (
        {"TP_RR": 26.0, "BE_RR": 0.01}
        if args.group in (
            "shape",
            "shape_core",
            "shape_final",
            "shape_combo",
            "body_cliff",
            "windows",
        )
        else {}
    )
    if args.group == "windows":
        optimized_payoff.update(
            {
                "PATH_EFFICIENCY_MIN": 0.22,
                "RELEASE_BODY_ATR_MIN": 0.80,
            }
        )
    probes = GROUPS[args.group]
    if args.probe:
        probes = tuple(item for item in probes if item[0] == args.probe)
        if not probes:
            parser.error(f"unknown probe {args.probe!r} in {args.group}")
    for name, override in probes:
        cfg = {**optimized_payoff, **override}
        summary, _ = backtest(
            369, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
