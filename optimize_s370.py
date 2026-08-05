# -*- coding: utf-8 -*-
"""Cross-window robustness probes for S370."""

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
        ("buy_only", {"ALLOW_SELL": False}),
        ("sell_only", {"ALLOW_BUY": False}),
        ("conc006", {"CONCENTRATION_MIN": 0.06}),
        ("conc010", {"CONCENTRATION_MIN": 0.10}),
        ("conc012", {"CONCENTRATION_MIN": 0.12}),
        ("ratio110", {"CONCENTRATION_RATIO_MIN": 1.10}),
        ("ratio130", {"CONCENTRATION_RATIO_MIN": 1.30}),
        ("energy014", {"DIRECTIONAL_ENERGY_MIN": 0.14}),
        ("energy022", {"DIRECTIONAL_ENERGY_MIN": 0.22}),
        ("energy026", {"DIRECTIONAL_ENERGY_MIN": 0.26}),
        ("path014", {"PATH_EFFICIENCY_MIN": 0.14}),
        ("path022", {"PATH_EFFICIENCY_MIN": 0.22}),
        ("body060", {"RELEASE_BODY_ATR_MIN": 0.60}),
        ("body080", {"RELEASE_BODY_ATR_MIN": 0.80}),
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
        ("path022", {"PATH_EFFICIENCY_MIN": 0.22}),
        (
            "path022_energy022",
            {
                "PATH_EFFICIENCY_MIN": 0.22,
                "DIRECTIONAL_ENERGY_MIN": 0.22,
            },
        ),
        (
            "path022_energy024",
            {
                "PATH_EFFICIENCY_MIN": 0.22,
                "DIRECTIONAL_ENERGY_MIN": 0.24,
            },
        ),
    ),
    "recent_local": (
        ("recent016", {"RECENT_BARS": 16}),
        ("recent018", {"RECENT_BARS": 18}),
        ("recent020", {"RECENT_BARS": 20}),
        ("recent022", {"RECENT_BARS": 22}),
        ("recent024", {"RECENT_BARS": 24}),
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
    base_cfg = {"BE_RR": 0.01} if args.group != "payoff" else {}
    if args.group in ("windows", "recent_local"):
        base_cfg.update(
            {
                "PATH_EFFICIENCY_MIN": 0.22,
                "DIRECTIONAL_ENERGY_MIN": 0.24,
            }
        )
    for name, override in GROUPS[args.group]:
        cfg = {**base_cfg, **override}
        summary, _ = backtest(
            370, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
