# -*- coding: utf-8 -*-
"""Cross-window robustness probes for S371."""

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
        ("skew035", {"SKEWNESS_MIN": 0.35}),
        ("skew055", {"SKEWNESS_MIN": 0.55}),
        ("skew070", {"SKEWNESS_MIN": 0.70}),
        ("ratio110", {"SKEWNESS_RATIO_MIN": 1.10}),
        ("ratio130", {"SKEWNESS_RATIO_MIN": 1.30}),
        ("ratio150", {"SKEWNESS_RATIO_MIN": 1.50}),
        ("path014", {"PATH_EFFICIENCY_MIN": 0.14}),
        ("path022", {"PATH_EFFICIENCY_MIN": 0.22}),
        ("path026", {"PATH_EFFICIENCY_MIN": 0.26}),
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
    "shape_combo": (
        (
            "skew070_path022",
            {"SKEWNESS_MIN": 0.70, "PATH_EFFICIENCY_MIN": 0.22},
        ),
        (
            "close085",
            {"RELEASE_CLOSE_FRACTION": 0.85},
        ),
        (
            "skew070_path022_close085",
            {
                "SKEWNESS_MIN": 0.70,
                "PATH_EFFICIENCY_MIN": 0.22,
                "RELEASE_CLOSE_FRACTION": 0.85,
            },
        ),
        (
            "body060_path022",
            {
                "RELEASE_BODY_ATR_MIN": 0.60,
                "PATH_EFFICIENCY_MIN": 0.22,
            },
        ),
        (
            "body060_close085",
            {
                "RELEASE_BODY_ATR_MIN": 0.60,
                "RELEASE_CLOSE_FRACTION": 0.85,
            },
        ),
        (
            "all",
            {
                "SKEWNESS_MIN": 0.70,
                "PATH_EFFICIENCY_MIN": 0.22,
                "RELEASE_BODY_ATR_MIN": 0.60,
                "RELEASE_CLOSE_FRACTION": 0.85,
            },
        ),
    ),
    "shape_cliff": (
        ("base", {}),
        ("close082", {"RELEASE_CLOSE_FRACTION": 0.82}),
        ("close088", {"RELEASE_CLOSE_FRACTION": 0.88}),
        ("close090", {"RELEASE_CLOSE_FRACTION": 0.90}),
        ("body050", {"RELEASE_BODY_ATR_MIN": 0.50}),
        ("body055", {"RELEASE_BODY_ATR_MIN": 0.55}),
        ("body065", {"RELEASE_BODY_ATR_MIN": 0.65}),
        ("body070", {"RELEASE_BODY_ATR_MIN": 0.70}),
    ),
    "baseline_local": (
        ("baseline040", {"BASELINE_BARS": 40}),
        ("baseline050", {"BASELINE_BARS": 50}),
        ("baseline060", {"BASELINE_BARS": 60}),
        ("baseline070", {"BASELINE_BARS": 70}),
        ("baseline080", {"BASELINE_BARS": 80}),
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
    base_cfg = {"BE_RR": 0.02} if args.group != "payoff" else {}
    if args.group == "shape_cliff":
        base_cfg.update(
            {
                "SKEWNESS_MIN": 0.70,
                "PATH_EFFICIENCY_MIN": 0.22,
                "RELEASE_BODY_ATR_MIN": 0.60,
                "RELEASE_CLOSE_FRACTION": 0.85,
            }
        )
    if args.group in ("windows", "baseline_local"):
        base_cfg.update(
            {
                "SKEWNESS_MIN": 0.70,
                "PATH_EFFICIENCY_MIN": 0.22,
                "RELEASE_BODY_ATR_MIN": 0.60,
                "RELEASE_CLOSE_FRACTION": 0.85,
            }
        )
    for name, override in GROUPS[args.group]:
        cfg = {**base_cfg, **override}
        summary, _ = backtest(
            371, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
