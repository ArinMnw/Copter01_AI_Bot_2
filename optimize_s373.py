# -*- coding: utf-8 -*-
"""Cross-window robustness probes for S373."""

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
        ("be008", {"BE_RR": 0.08}),
        ("be012", {"BE_RR": 0.12}),
        ("rr7_be001", {"TP_RR": 7.0, "BE_RR": 0.01}),
        ("rr9_be001", {"TP_RR": 9.0, "BE_RR": 0.01}),
    ),
    "shape": (
        ("base", {}),
        ("impact110", {"IMPACT_RATIO_MIN": 1.10}),
        ("impact140", {"IMPACT_RATIO_MIN": 1.40}),
        ("impact160", {"IMPACT_RATIO_MIN": 1.60}),
        ("direction020", {"DIRECTIONAL_IMPACT_MIN": 0.20}),
        ("direction040", {"DIRECTIONAL_IMPACT_MIN": 0.40}),
        ("direction050", {"DIRECTIONAL_IMPACT_MIN": 0.50}),
        ("volume100", {"VOLUME_RATIO_MAX": 1.00}),
        ("volume130", {"VOLUME_RATIO_MAX": 1.30}),
        ("volume200", {"VOLUME_RATIO_MAX": 2.00}),
        ("path018", {"PATH_EFFICIENCY_MIN": 0.18}),
        ("path026", {"PATH_EFFICIENCY_MIN": 0.26}),
        ("body050", {"RELEASE_BODY_ATR_MIN": 0.50}),
        ("body080", {"RELEASE_BODY_ATR_MIN": 0.80}),
        ("close075", {"RELEASE_CLOSE_FRACTION": 0.75}),
        ("close085", {"RELEASE_CLOSE_FRACTION": 0.85}),
    ),
    "windows": (
        ("base", {}),
        ("baseline040", {"BASELINE_BARS": 40}),
        ("baseline080", {"BASELINE_BARS": 80}),
        ("baseline100", {"BASELINE_BARS": 100}),
        ("recent016", {"RECENT_BARS": 16}),
        ("recent024", {"RECENT_BARS": 24}),
        ("net040", {"NET_MOVE_ATR_MIN": 0.40}),
        ("net060", {"NET_MOVE_ATR_MIN": 0.60}),
    ),
    "rr_cliff": (
        ("rr10", {"TP_RR": 10.0}),
        ("rr11", {"TP_RR": 11.0}),
        ("rr12", {"TP_RR": 12.0}),
        ("rr14", {"TP_RR": 14.0}),
        ("rr16", {"TP_RR": 16.0}),
        ("rr20", {"TP_RR": 20.0}),
    ),
    "interaction": (
        ("base", {}),
        ("direction020", {"DIRECTIONAL_IMPACT_MIN": 0.20}),
        ("impact110", {"IMPACT_RATIO_MIN": 1.10}),
        (
            "direction020_impact110",
            {
                "DIRECTIONAL_IMPACT_MIN": 0.20,
                "IMPACT_RATIO_MIN": 1.10,
            },
        ),
        (
            "direction020_path026",
            {
                "DIRECTIONAL_IMPACT_MIN": 0.20,
                "PATH_EFFICIENCY_MIN": 0.26,
            },
        ),
        (
            "direction020_body080",
            {
                "DIRECTIONAL_IMPACT_MIN": 0.20,
                "RELEASE_BODY_ATR_MIN": 0.80,
            },
        ),
        (
            "direction020_close085",
            {
                "DIRECTIONAL_IMPACT_MIN": 0.20,
                "RELEASE_CLOSE_FRACTION": 0.85,
            },
        ),
        (
            "direction020_quality",
            {
                "DIRECTIONAL_IMPACT_MIN": 0.20,
                "PATH_EFFICIENCY_MIN": 0.26,
                "RELEASE_BODY_ATR_MIN": 0.80,
                "RELEASE_CLOSE_FRACTION": 0.85,
            },
        ),
    ),
    "local": (
        (
            "d020_i110",
            {
                "DIRECTIONAL_IMPACT_MIN": 0.20,
                "IMPACT_RATIO_MIN": 1.10,
            },
        ),
        (
            "d020_i105",
            {
                "DIRECTIONAL_IMPACT_MIN": 0.20,
                "IMPACT_RATIO_MIN": 1.05,
            },
        ),
        (
            "d020_i115",
            {
                "DIRECTIONAL_IMPACT_MIN": 0.20,
                "IMPACT_RATIO_MIN": 1.15,
            },
        ),
        (
            "d020_i120",
            {
                "DIRECTIONAL_IMPACT_MIN": 0.20,
                "IMPACT_RATIO_MIN": 1.20,
            },
        ),
        (
            "d015_i110",
            {
                "DIRECTIONAL_IMPACT_MIN": 0.15,
                "IMPACT_RATIO_MIN": 1.10,
            },
        ),
        (
            "d025_i110",
            {
                "DIRECTIONAL_IMPACT_MIN": 0.25,
                "IMPACT_RATIO_MIN": 1.10,
            },
        ),
        (
            "d020_i110_path026",
            {
                "DIRECTIONAL_IMPACT_MIN": 0.20,
                "IMPACT_RATIO_MIN": 1.10,
                "PATH_EFFICIENCY_MIN": 0.26,
            },
        ),
    ),
    "local2": (
        (
            "d015_i110",
            {
                "DIRECTIONAL_IMPACT_MIN": 0.15,
                "IMPACT_RATIO_MIN": 1.10,
            },
        ),
        (
            "d010_i110",
            {
                "DIRECTIONAL_IMPACT_MIN": 0.10,
                "IMPACT_RATIO_MIN": 1.10,
            },
        ),
        (
            "d012_i110",
            {
                "DIRECTIONAL_IMPACT_MIN": 0.12,
                "IMPACT_RATIO_MIN": 1.10,
            },
        ),
        (
            "d018_i110",
            {
                "DIRECTIONAL_IMPACT_MIN": 0.18,
                "IMPACT_RATIO_MIN": 1.10,
            },
        ),
        (
            "d015_i110_path026",
            {
                "DIRECTIONAL_IMPACT_MIN": 0.15,
                "IMPACT_RATIO_MIN": 1.10,
                "PATH_EFFICIENCY_MIN": 0.26,
            },
        ),
        (
            "d015_i110_body080",
            {
                "DIRECTIONAL_IMPACT_MIN": 0.15,
                "IMPACT_RATIO_MIN": 1.10,
                "RELEASE_BODY_ATR_MIN": 0.80,
            },
        ),
        (
            "d015_i110_path026_body080",
            {
                "DIRECTIONAL_IMPACT_MIN": 0.15,
                "IMPACT_RATIO_MIN": 1.10,
                "PATH_EFFICIENCY_MIN": 0.26,
                "RELEASE_BODY_ATR_MIN": 0.80,
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
            373,
            months,
            "M5",
            0.20,
            0.01,
            end,
            300,
            cfg,
            prepared,
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
