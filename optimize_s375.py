# -*- coding: utf-8 -*-
"""Breadth and falsification probes for S375."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
}

GROUPS = {
    "breadth": (
        ("base", {}),
        ("impact070", {"IMPACT_CONTRACTION_MAX": 0.70}),
        ("impact095", {"IMPACT_CONTRACTION_MAX": 0.95}),
        ("impact105", {"IMPACT_CONTRACTION_MAX": 1.05}),
        ("volume090", {"VOLUME_EXPANSION_MIN": 0.90}),
        ("volume100", {"VOLUME_EXPANSION_MIN": 1.00}),
        ("volume120", {"VOLUME_EXPANSION_MIN": 1.20}),
        ("direction010", {"DIRECTIONAL_VOLUME_MIN": 0.10}),
        ("direction030", {"DIRECTIONAL_VOLUME_MIN": 0.30}),
        ("path010", {"PATH_EFFICIENCY_MIN": 0.10}),
        ("path020", {"PATH_EFFICIENCY_MIN": 0.20}),
        ("body015", {"REJECTION_BODY_ATR_MIN": 0.15}),
        ("body035", {"REJECTION_BODY_ATR_MIN": 0.35}),
        ("wick020", {"REJECTION_WICK_FRACTION_MIN": 0.20}),
        ("wick040", {"REJECTION_WICK_FRACTION_MIN": 0.40}),
        ("close050", {"REJECTION_CLOSE_FRACTION": 0.50}),
        ("close065", {"REJECTION_CLOSE_FRACTION": 0.65}),
    ),
    "interaction": (
        ("body015", {"REJECTION_BODY_ATR_MIN": 0.15}),
        (
            "body015_path010",
            {
                "REJECTION_BODY_ATR_MIN": 0.15,
                "PATH_EFFICIENCY_MIN": 0.10,
            },
        ),
        (
            "body015_impact070",
            {
                "REJECTION_BODY_ATR_MIN": 0.15,
                "IMPACT_CONTRACTION_MAX": 0.70,
            },
        ),
        (
            "body015_direction010",
            {
                "REJECTION_BODY_ATR_MIN": 0.15,
                "DIRECTIONAL_VOLUME_MIN": 0.10,
            },
        ),
        (
            "body015_wick020",
            {
                "REJECTION_BODY_ATR_MIN": 0.15,
                "REJECTION_WICK_FRACTION_MIN": 0.20,
            },
        ),
        (
            "body015_path010_impact070",
            {
                "REJECTION_BODY_ATR_MIN": 0.15,
                "PATH_EFFICIENCY_MIN": 0.10,
                "IMPACT_CONTRACTION_MAX": 0.70,
            },
        ),
        (
            "body015_direction010_wick020",
            {
                "REJECTION_BODY_ATR_MIN": 0.15,
                "DIRECTIONAL_VOLUME_MIN": 0.10,
                "REJECTION_WICK_FRACTION_MIN": 0.20,
            },
        ),
    ),
    "payoff_survivor": (
        ("base", {"REJECTION_BODY_ATR_MIN": 0.15, "PATH_EFFICIENCY_MIN": 0.10}),
        ("buy_only", {"REJECTION_BODY_ATR_MIN": 0.15, "PATH_EFFICIENCY_MIN": 0.10, "ALLOW_SELL": False}),
        ("sell_only", {"REJECTION_BODY_ATR_MIN": 0.15, "PATH_EFFICIENCY_MIN": 0.10, "ALLOW_BUY": False}),
        ("rr8", {"REJECTION_BODY_ATR_MIN": 0.15, "PATH_EFFICIENCY_MIN": 0.10, "TP_RR": 8.0}),
        ("rr9", {"REJECTION_BODY_ATR_MIN": 0.15, "PATH_EFFICIENCY_MIN": 0.10, "TP_RR": 9.0}),
        ("be001", {"REJECTION_BODY_ATR_MIN": 0.15, "PATH_EFFICIENCY_MIN": 0.10, "BE_RR": 0.01}),
        ("be002", {"REJECTION_BODY_ATR_MIN": 0.15, "PATH_EFFICIENCY_MIN": 0.10, "BE_RR": 0.02}),
        ("be008", {"REJECTION_BODY_ATR_MIN": 0.15, "PATH_EFFICIENCY_MIN": 0.10, "BE_RR": 0.08}),
        ("be012", {"REJECTION_BODY_ATR_MIN": 0.15, "PATH_EFFICIENCY_MIN": 0.10, "BE_RR": 0.12}),
    ),
    "local": (
        ("base", {}),
        ("body010", {"REJECTION_BODY_ATR_MIN": 0.10}),
        ("body012", {"REJECTION_BODY_ATR_MIN": 0.12}),
        ("body018", {"REJECTION_BODY_ATR_MIN": 0.18}),
        ("body020", {"REJECTION_BODY_ATR_MIN": 0.20}),
        ("path005", {"PATH_EFFICIENCY_MIN": 0.05}),
        ("path008", {"PATH_EFFICIENCY_MIN": 0.08}),
        ("path012", {"PATH_EFFICIENCY_MIN": 0.12}),
        ("path015", {"PATH_EFFICIENCY_MIN": 0.15}),
    ),
    "windows": (
        ("base", {}),
        ("baseline040", {"BASELINE_BARS": 40}),
        ("baseline080", {"BASELINE_BARS": 80}),
        ("baseline100", {"BASELINE_BARS": 100}),
        ("recent016", {"RECENT_BARS": 16}),
        ("recent024", {"RECENT_BARS": 24}),
        ("net030", {"NET_MOVE_ATR_MIN": 0.30}),
        ("net050", {"NET_MOVE_ATR_MIN": 0.50}),
    ),
    "local_combo": (
        ("body015_path010", {"REJECTION_BODY_ATR_MIN": 0.15, "PATH_EFFICIENCY_MIN": 0.10}),
        ("body015_path012", {"REJECTION_BODY_ATR_MIN": 0.15, "PATH_EFFICIENCY_MIN": 0.12}),
        ("body012_path010", {"REJECTION_BODY_ATR_MIN": 0.12, "PATH_EFFICIENCY_MIN": 0.10}),
        ("body012_path012", {"REJECTION_BODY_ATR_MIN": 0.12, "PATH_EFFICIENCY_MIN": 0.12}),
        ("body010_path012", {"REJECTION_BODY_ATR_MIN": 0.10, "PATH_EFFICIENCY_MIN": 0.12}),
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
            375,
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
