# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S382."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
}

CORE = {
    "BASELINE_BARS": 80,
    "RECENT_BARS": 28,
    "CORRELATION_RISE_MIN": 0.10,
    "EVENT_VOLUME_RATIO_MIN": 1.05,
    "EVENT_BODY_FRACTION_MIN": 0.70,
    "BE_RR": 0.01,
}

GROUPS = {
    "payoff": (
        ("base", {}),
        ("buy_only", {"ALLOW_SELL": False}),
        ("sell_only", {"ALLOW_BUY": False}),
        ("rr8", {"TP_RR": 8.0}),
        ("rr9", {"TP_RR": 9.0}),
        ("rr10", {"TP_RR": 10.0}),
        ("be001", {"BE_RR": 0.01}),
        ("be005", {"BE_RR": 0.05}),
        ("be008", {"BE_RR": 0.08}),
        ("be012", {"BE_RR": 0.12}),
    ),
    "coupling": (
        ("base", {}),
        ("corr015", {"RECENT_CORRELATION_MIN": 0.15}),
        ("corr025", {"RECENT_CORRELATION_MIN": 0.25}),
        ("corr040", {"RECENT_CORRELATION_MIN": 0.40}),
        ("corr050", {"RECENT_CORRELATION_MIN": 0.50}),
        ("rise010", {"CORRELATION_RISE_MIN": 0.10}),
        ("rise030", {"CORRELATION_RISE_MIN": 0.30}),
        ("rise040", {"CORRELATION_RISE_MIN": 0.40}),
        ("direction010", {"DIRECTIONAL_VOLUME_MIN": 0.10}),
        ("direction020", {"DIRECTIONAL_VOLUME_MIN": 0.20}),
        ("path012", {"PATH_EFFICIENCY_MIN": 0.12}),
        ("path028", {"PATH_EFFICIENCY_MIN": 0.28}),
        ("net030", {"NET_MOVE_ATR_MIN": 0.30}),
        ("net060", {"NET_MOVE_ATR_MIN": 0.60}),
    ),
    "event": (
        ("base", {}),
        ("volume075", {"EVENT_VOLUME_RATIO_MIN": 0.75}),
        ("volume105", {"EVENT_VOLUME_RATIO_MIN": 1.05}),
        ("body035", {"EVENT_BODY_ATR_MIN": 0.35}),
        ("body065", {"EVENT_BODY_ATR_MIN": 0.65}),
        ("range055", {"EVENT_RANGE_ATR_MIN": 0.55}),
        ("range085", {"EVENT_RANGE_ATR_MIN": 0.85}),
        ("fraction050", {"EVENT_BODY_FRACTION_MIN": 0.50}),
        ("fraction070", {"EVENT_BODY_FRACTION_MIN": 0.70}),
        ("close065", {"EVENT_CLOSE_FRACTION": 0.65}),
        ("close085", {"EVENT_CLOSE_FRACTION": 0.85}),
    ),
    "windows": (
        ("base", {}),
        ("baseline040", {"BASELINE_BARS": 40}),
        ("baseline080", {"BASELINE_BARS": 80}),
        ("baseline100", {"BASELINE_BARS": 100}),
        ("recent016", {"RECENT_BARS": 16}),
        ("recent024", {"RECENT_BARS": 24}),
        ("recent028", {"RECENT_BARS": 28}),
    ),
    "focused": (
        ("base", {}),
        ("b80_rise", {"BASELINE_BARS": 80, "CORRELATION_RISE_MIN": 0.10}),
        ("b80_rise_v105", {"BASELINE_BARS": 80, "CORRELATION_RISE_MIN": 0.10, "EVENT_VOLUME_RATIO_MIN": 1.05}),
        ("b80_rise_v105_f70", {"BASELINE_BARS": 80, "CORRELATION_RISE_MIN": 0.10, "EVENT_VOLUME_RATIO_MIN": 1.05, "EVENT_BODY_FRACTION_MIN": 0.70}),
        ("core_be", {"BASELINE_BARS": 80, "CORRELATION_RISE_MIN": 0.10, "EVENT_VOLUME_RATIO_MIN": 1.05, "EVENT_BODY_FRACTION_MIN": 0.70, "BE_RR": 0.01}),
        ("core_r28", {"BASELINE_BARS": 80, "RECENT_BARS": 28, "CORRELATION_RISE_MIN": 0.10, "EVENT_VOLUME_RATIO_MIN": 1.05, "EVENT_BODY_FRACTION_MIN": 0.70, "BE_RR": 0.01}),
        ("core_dir", {"BASELINE_BARS": 80, "CORRELATION_RISE_MIN": 0.10, "DIRECTIONAL_VOLUME_MIN": 0.20, "EVENT_VOLUME_RATIO_MIN": 1.05, "EVENT_BODY_FRACTION_MIN": 0.70, "BE_RR": 0.01}),
        ("core_path", {"BASELINE_BARS": 80, "CORRELATION_RISE_MIN": 0.10, "PATH_EFFICIENCY_MIN": 0.28, "EVENT_VOLUME_RATIO_MIN": 1.05, "EVENT_BODY_FRACTION_MIN": 0.70, "BE_RR": 0.01}),
        ("core_all", {"BASELINE_BARS": 80, "RECENT_BARS": 28, "CORRELATION_RISE_MIN": 0.10, "DIRECTIONAL_VOLUME_MIN": 0.20, "PATH_EFFICIENCY_MIN": 0.28, "EVENT_VOLUME_RATIO_MIN": 1.05, "EVENT_BODY_FRACTION_MIN": 0.70, "BE_RR": 0.01}),
    ),
    "local": (
        ("core", CORE),
        ("baseline100", {**CORE, "BASELINE_BARS": 100}),
        ("recent024", {**CORE, "RECENT_BARS": 24}),
        ("rise005", {**CORE, "CORRELATION_RISE_MIN": 0.05}),
        ("rise015", {**CORE, "CORRELATION_RISE_MIN": 0.15}),
        ("volume095", {**CORE, "EVENT_VOLUME_RATIO_MIN": 0.95}),
        ("volume115", {**CORE, "EVENT_VOLUME_RATIO_MIN": 1.15}),
        ("fraction065", {**CORE, "EVENT_BODY_FRACTION_MIN": 0.65}),
        ("fraction075", {**CORE, "EVENT_BODY_FRACTION_MIN": 0.75}),
        ("buffer004", {**CORE, "SL_BUFFER_ATR": 0.04}),
        ("buffer012", {**CORE, "SL_BUFFER_ATR": 0.12}),
        ("buffer016", {**CORE, "SL_BUFFER_ATR": 0.16}),
    ),
    "final": (
        ("core", CORE),
        ("v115_b016", {**CORE, "EVENT_VOLUME_RATIO_MIN": 1.15, "SL_BUFFER_ATR": 0.16}),
        ("rise015_b016", {**CORE, "CORRELATION_RISE_MIN": 0.15, "SL_BUFFER_ATR": 0.16}),
        ("rise015_v115_b016", {**CORE, "CORRELATION_RISE_MIN": 0.15, "EVENT_VOLUME_RATIO_MIN": 1.15, "SL_BUFFER_ATR": 0.16}),
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
            382,
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
