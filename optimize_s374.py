# -*- coding: utf-8 -*-
"""Cross-window robustness probes for S374."""

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
        ("direction015", {"DIRECTIONAL_VOLUME_MIN": 0.15}),
        ("direction020", {"DIRECTIONAL_VOLUME_MIN": 0.20}),
        ("direction030", {"DIRECTIONAL_VOLUME_MIN": 0.30}),
        ("direction035", {"DIRECTIONAL_VOLUME_MIN": 0.35}),
        ("ratio105", {"DIRECTIONAL_VOLUME_RATIO_MIN": 1.05}),
        ("ratio140", {"DIRECTIONAL_VOLUME_RATIO_MIN": 1.40}),
        ("ratio160", {"DIRECTIONAL_VOLUME_RATIO_MIN": 1.60}),
        ("volume090", {"VOLUME_EXPANSION_MIN": 0.90}),
        ("volume115", {"VOLUME_EXPANSION_MIN": 1.15}),
        ("volume130", {"VOLUME_EXPANSION_MIN": 1.30}),
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
    "interaction": (
        ("base", {}),
        ("ratio160", {"DIRECTIONAL_VOLUME_RATIO_MIN": 1.60}),
        ("path026", {"PATH_EFFICIENCY_MIN": 0.26}),
        ("volume090", {"VOLUME_EXPANSION_MIN": 0.90}),
        (
            "ratio160_path026",
            {
                "DIRECTIONAL_VOLUME_RATIO_MIN": 1.60,
                "PATH_EFFICIENCY_MIN": 0.26,
            },
        ),
        (
            "volume090_ratio160",
            {
                "VOLUME_EXPANSION_MIN": 0.90,
                "DIRECTIONAL_VOLUME_RATIO_MIN": 1.60,
            },
        ),
        (
            "volume090_path026",
            {
                "VOLUME_EXPANSION_MIN": 0.90,
                "PATH_EFFICIENCY_MIN": 0.26,
            },
        ),
        (
            "volume090_ratio160_path026",
            {
                "VOLUME_EXPANSION_MIN": 0.90,
                "DIRECTIONAL_VOLUME_RATIO_MIN": 1.60,
                "PATH_EFFICIENCY_MIN": 0.26,
            },
        ),
        (
            "volume090_ratio160_path026_body080",
            {
                "VOLUME_EXPANSION_MIN": 0.90,
                "DIRECTIONAL_VOLUME_RATIO_MIN": 1.60,
                "PATH_EFFICIENCY_MIN": 0.26,
                "RELEASE_BODY_ATR_MIN": 0.80,
            },
        ),
    ),
    "local": (
        (
            "base_combo",
            {
                "VOLUME_EXPANSION_MIN": 0.90,
                "DIRECTIONAL_VOLUME_RATIO_MIN": 1.60,
                "PATH_EFFICIENCY_MIN": 0.26,
                "RELEASE_BODY_ATR_MIN": 0.80,
            },
        ),
        (
            "ratio140",
            {
                "VOLUME_EXPANSION_MIN": 0.90,
                "DIRECTIONAL_VOLUME_RATIO_MIN": 1.40,
                "PATH_EFFICIENCY_MIN": 0.26,
                "RELEASE_BODY_ATR_MIN": 0.80,
            },
        ),
        (
            "ratio180",
            {
                "VOLUME_EXPANSION_MIN": 0.90,
                "DIRECTIONAL_VOLUME_RATIO_MIN": 1.80,
                "PATH_EFFICIENCY_MIN": 0.26,
                "RELEASE_BODY_ATR_MIN": 0.80,
            },
        ),
        (
            "volume085",
            {
                "VOLUME_EXPANSION_MIN": 0.85,
                "DIRECTIONAL_VOLUME_RATIO_MIN": 1.60,
                "PATH_EFFICIENCY_MIN": 0.26,
                "RELEASE_BODY_ATR_MIN": 0.80,
            },
        ),
        (
            "volume095",
            {
                "VOLUME_EXPANSION_MIN": 0.95,
                "DIRECTIONAL_VOLUME_RATIO_MIN": 1.60,
                "PATH_EFFICIENCY_MIN": 0.26,
                "RELEASE_BODY_ATR_MIN": 0.80,
            },
        ),
        (
            "volume100",
            {
                "VOLUME_EXPANSION_MIN": 1.00,
                "DIRECTIONAL_VOLUME_RATIO_MIN": 1.60,
                "PATH_EFFICIENCY_MIN": 0.26,
                "RELEASE_BODY_ATR_MIN": 0.80,
            },
        ),
        (
            "path024",
            {
                "VOLUME_EXPANSION_MIN": 0.90,
                "DIRECTIONAL_VOLUME_RATIO_MIN": 1.60,
                "PATH_EFFICIENCY_MIN": 0.24,
                "RELEASE_BODY_ATR_MIN": 0.80,
            },
        ),
        (
            "path028",
            {
                "VOLUME_EXPANSION_MIN": 0.90,
                "DIRECTIONAL_VOLUME_RATIO_MIN": 1.60,
                "PATH_EFFICIENCY_MIN": 0.28,
                "RELEASE_BODY_ATR_MIN": 0.80,
            },
        ),
        (
            "body075",
            {
                "VOLUME_EXPANSION_MIN": 0.90,
                "DIRECTIONAL_VOLUME_RATIO_MIN": 1.60,
                "PATH_EFFICIENCY_MIN": 0.26,
                "RELEASE_BODY_ATR_MIN": 0.75,
            },
        ),
        (
            "body085",
            {
                "VOLUME_EXPANSION_MIN": 0.90,
                "DIRECTIONAL_VOLUME_RATIO_MIN": 1.60,
                "PATH_EFFICIENCY_MIN": 0.26,
                "RELEASE_BODY_ATR_MIN": 0.85,
            },
        ),
    ),
    "body_cliff": (
        (
            "body080",
            {
                "VOLUME_EXPANSION_MIN": 0.90,
                "DIRECTIONAL_VOLUME_RATIO_MIN": 1.60,
                "PATH_EFFICIENCY_MIN": 0.26,
                "RELEASE_BODY_ATR_MIN": 0.80,
            },
        ),
        (
            "body082",
            {
                "VOLUME_EXPANSION_MIN": 0.90,
                "DIRECTIONAL_VOLUME_RATIO_MIN": 1.60,
                "PATH_EFFICIENCY_MIN": 0.26,
                "RELEASE_BODY_ATR_MIN": 0.82,
            },
        ),
        (
            "body085",
            {
                "VOLUME_EXPANSION_MIN": 0.90,
                "DIRECTIONAL_VOLUME_RATIO_MIN": 1.60,
                "PATH_EFFICIENCY_MIN": 0.26,
                "RELEASE_BODY_ATR_MIN": 0.85,
            },
        ),
        (
            "body088",
            {
                "VOLUME_EXPANSION_MIN": 0.90,
                "DIRECTIONAL_VOLUME_RATIO_MIN": 1.60,
                "PATH_EFFICIENCY_MIN": 0.26,
                "RELEASE_BODY_ATR_MIN": 0.88,
            },
        ),
        (
            "body090",
            {
                "VOLUME_EXPANSION_MIN": 0.90,
                "DIRECTIONAL_VOLUME_RATIO_MIN": 1.60,
                "PATH_EFFICIENCY_MIN": 0.26,
                "RELEASE_BODY_ATR_MIN": 0.90,
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
            374,
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
