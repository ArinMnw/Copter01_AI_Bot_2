# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S403."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
    "latest": (2, "2026-07-30T00:00:00+07:00"),
}

GROUPS = {
    "direction": (
        ("fade", {}),
        ("continuation", {"FADE_DOMINANCE": False}),
        ("fade_dom058", {"DOMINANCE_MIN": 0.58}),
        ("fade_dom066", {"DOMINANCE_MIN": 0.66}),
        ("fade_ratio100", {"DOMINANCE_RATIO_MIN": 1.00}),
        ("fade_ratio108", {"DOMINANCE_RATIO_MIN": 1.08}),
        ("fade_rise000", {"DOMINANCE_RISE_MIN": 0.00}),
        ("fade_rise050", {"DOMINANCE_RISE_MIN": 0.05}),
        ("fade_energy000", {"DOMINANT_ENERGY_ATR2_MIN": 0.00}),
        ("fade_energy100", {"DOMINANT_ENERGY_ATR2_MIN": 0.10}),
        ("fade_recent024", {"BASELINE_BARS": 72, "RECENT_BARS": 24}),
        ("fade_recent032", {"BASELINE_BARS": 96, "RECENT_BARS": 32}),
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
        ("buffer014", {"SL_BUFFER_ATR": 0.14}),
        ("buffer022", {"SL_BUFFER_ATR": 0.22}),
    ),
    "continuation": (
        ("base", {"FADE_DOMINANCE": False}),
        ("dom058", {"FADE_DOMINANCE": False, "DOMINANCE_MIN": 0.58}),
        ("dom066", {"FADE_DOMINANCE": False, "DOMINANCE_MIN": 0.66}),
        ("dom070", {"FADE_DOMINANCE": False, "DOMINANCE_MIN": 0.70}),
        ("ratio100", {"FADE_DOMINANCE": False, "DOMINANCE_RATIO_MIN": 1.00}),
        ("ratio108", {"FADE_DOMINANCE": False, "DOMINANCE_RATIO_MIN": 1.08}),
        ("ratio112", {"FADE_DOMINANCE": False, "DOMINANCE_RATIO_MIN": 1.12}),
        ("rise000", {"FADE_DOMINANCE": False, "DOMINANCE_RISE_MIN": 0.00}),
        ("rise050", {"FADE_DOMINANCE": False, "DOMINANCE_RISE_MIN": 0.05}),
        ("rise080", {"FADE_DOMINANCE": False, "DOMINANCE_RISE_MIN": 0.08}),
        ("energy100", {"FADE_DOMINANCE": False,
                       "DOMINANT_ENERGY_ATR2_MIN": 0.10}),
        ("recent024", {"FADE_DOMINANCE": False, "BASELINE_BARS": 72,
                       "RECENT_BARS": 24}),
        ("recent032", {"FADE_DOMINANCE": False, "BASELINE_BARS": 96,
                       "RECENT_BARS": 32}),
    ),
    "focused": (
        ("base", {}),
        ("dom066", {"DOMINANCE_MIN": 0.66}),
        ("dom070", {"DOMINANCE_MIN": 0.70}),
        ("dom074", {"DOMINANCE_MIN": 0.74}),
        ("ratio108", {"DOMINANCE_RATIO_MIN": 1.08}),
        ("ratio112", {"DOMINANCE_RATIO_MIN": 1.12}),
        ("rise050", {"DOMINANCE_RISE_MIN": 0.05}),
        ("rise080", {"DOMINANCE_RISE_MIN": 0.08}),
        ("dom070_ratio108", {"DOMINANCE_MIN": 0.70,
                             "DOMINANCE_RATIO_MIN": 1.08}),
        ("dom070_rise050", {"DOMINANCE_MIN": 0.70,
                            "DOMINANCE_RISE_MIN": 0.05}),
    ),
    "dominance_local": (
        ("d065", {"DOMINANCE_MIN": 0.65}),
        ("d066", {"DOMINANCE_MIN": 0.66}),
        ("d067", {"DOMINANCE_MIN": 0.67}),
        ("d068", {"DOMINANCE_MIN": 0.68}),
        ("d069", {"DOMINANCE_MIN": 0.69}),
        ("d070", {"DOMINANCE_MIN": 0.70}),
    ),
    "buffer_local": (
        ("b014", {"SL_BUFFER_ATR": 0.14}),
        ("b016", {"SL_BUFFER_ATR": 0.16}),
        ("b018", {"SL_BUFFER_ATR": 0.18}),
        ("b020", {"SL_BUFFER_ATR": 0.20}),
        ("b022", {"SL_BUFFER_ATR": 0.22}),
        ("b024", {"SL_BUFFER_ATR": 0.24}),
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
            403, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
