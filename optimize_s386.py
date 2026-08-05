# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S386."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
}

GROUPS = {
    "hazard": (
        ("base", {}),
        ("fast025", {"FAST_ALPHA": 0.25}),
        ("fast045", {"FAST_ALPHA": 0.45}),
        ("slow005", {"SLOW_ALPHA": 0.05}),
        ("slow015", {"SLOW_ALPHA": 0.15}),
        ("rise000", {"HAZARD_RISE_MIN": 0.00}),
        ("rise100", {"HAZARD_RISE_MIN": 0.10}),
        ("accel000", {"HAZARD_ACCELERATION_MIN": 0.00}),
        ("accel060", {"HAZARD_ACCELERATION_MIN": 0.06}),
        ("direction010", {"TAIL_DIRECTIONAL_VOLUME_MIN": 0.10}),
        ("direction025", {"TAIL_DIRECTIONAL_VOLUME_MIN": 0.25}),
    ),
    "payoff": (
        ("base", {}),
        ("buy_only", {"ALLOW_SELL": False}),
        ("sell_only", {"ALLOW_BUY": False}),
        ("rr8", {"TP_RR": 8.0}),
        ("rr9", {"TP_RR": 9.0}),
        ("rr10", {"TP_RR": 10.0}),
        ("be001", {"BE_RR": 0.01}),
        ("be005", {"BE_RR": 0.05}),
        ("be010", {"BE_RR": 0.10}),
    ),
    "breadth": (
        ("base", {}),
        ("q055", {"TAIL_QUANTILE": 0.55}),
        ("q065", {"TAIL_QUANTILE": 0.65}),
        ("baseline060", {"BASELINE_BARS": 60}),
        ("baseline100", {"BASELINE_BARS": 100}),
        ("recent016", {"RECENT_BARS": 16}),
        ("recent024", {"RECENT_BARS": 24}),
        ("body055", {"EVENT_BODY_ATR_MIN": 0.55}),
        ("body075", {"EVENT_BODY_ATR_MIN": 0.75}),
        ("fraction068", {"EVENT_BODY_FRACTION_MIN": 0.68}),
        ("fraction075", {"EVENT_BODY_FRACTION_MIN": 0.75}),
    ),
    "focused": (
        ("base", {}),
        ("rise100", {"HAZARD_RISE_MIN": 0.10}),
        ("accel060", {"HAZARD_ACCELERATION_MIN": 0.06}),
        ("rise100_accel060", {"HAZARD_RISE_MIN": 0.10, "HAZARD_ACCELERATION_MIN": 0.06}),
        ("b060", {"BASELINE_BARS": 60}),
        ("f075", {"EVENT_BODY_FRACTION_MIN": 0.75}),
        ("b060_f075", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.75}),
        ("all", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.75, "HAZARD_RISE_MIN": 0.10, "HAZARD_ACCELERATION_MIN": 0.06}),
    ),
    "local": (
        ("core", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.75, "HAZARD_RISE_MIN": 0.10, "HAZARD_ACCELERATION_MIN": 0.06}),
        ("baseline050", {"BASELINE_BARS": 50, "EVENT_BODY_FRACTION_MIN": 0.75, "HAZARD_RISE_MIN": 0.10, "HAZARD_ACCELERATION_MIN": 0.06}),
        ("baseline070", {"BASELINE_BARS": 70, "EVENT_BODY_FRACTION_MIN": 0.75, "HAZARD_RISE_MIN": 0.10, "HAZARD_ACCELERATION_MIN": 0.06}),
        ("fraction073", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.73, "HAZARD_RISE_MIN": 0.10, "HAZARD_ACCELERATION_MIN": 0.06}),
        ("fraction074", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.74, "HAZARD_RISE_MIN": 0.10, "HAZARD_ACCELERATION_MIN": 0.06}),
        ("fraction076", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.76, "HAZARD_RISE_MIN": 0.10, "HAZARD_ACCELERATION_MIN": 0.06}),
        ("fraction077", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.77, "HAZARD_RISE_MIN": 0.10, "HAZARD_ACCELERATION_MIN": 0.06}),
        ("rise080", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.75, "HAZARD_RISE_MIN": 0.08, "HAZARD_ACCELERATION_MIN": 0.06}),
        ("rise120", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.75, "HAZARD_RISE_MIN": 0.12, "HAZARD_ACCELERATION_MIN": 0.06}),
        ("accel040", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.75, "HAZARD_RISE_MIN": 0.10, "HAZARD_ACCELERATION_MIN": 0.04}),
        ("accel080", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.75, "HAZARD_RISE_MIN": 0.10, "HAZARD_ACCELERATION_MIN": 0.08}),
        ("fast030", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.75, "HAZARD_RISE_MIN": 0.10, "HAZARD_ACCELERATION_MIN": 0.06, "FAST_ALPHA": 0.30}),
        ("fast040", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.75, "HAZARD_RISE_MIN": 0.10, "HAZARD_ACCELERATION_MIN": 0.06, "FAST_ALPHA": 0.40}),
        ("buffer016", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.75, "HAZARD_RISE_MIN": 0.10, "HAZARD_ACCELERATION_MIN": 0.06, "SL_BUFFER_ATR": 0.16}),
        ("buffer018", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.75, "HAZARD_RISE_MIN": 0.10, "HAZARD_ACCELERATION_MIN": 0.06, "SL_BUFFER_ATR": 0.18}),
        ("buffer020", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.75, "HAZARD_RISE_MIN": 0.10, "HAZARD_ACCELERATION_MIN": 0.06, "SL_BUFFER_ATR": 0.20}),
        ("buffer022", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.75, "HAZARD_RISE_MIN": 0.10, "HAZARD_ACCELERATION_MIN": 0.06, "SL_BUFFER_ATR": 0.22}),
    ),
    "final": (
        ("core", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.75, "HAZARD_RISE_MIN": 0.10, "HAZARD_ACCELERATION_MIN": 0.06}),
        ("f077", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.77, "HAZARD_RISE_MIN": 0.10, "HAZARD_ACCELERATION_MIN": 0.06}),
        ("rise120", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.75, "HAZARD_RISE_MIN": 0.12, "HAZARD_ACCELERATION_MIN": 0.06}),
        ("f077_rise120", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.77, "HAZARD_RISE_MIN": 0.12, "HAZARD_ACCELERATION_MIN": 0.06}),
        ("all2", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.77, "HAZARD_RISE_MIN": 0.12, "HAZARD_ACCELERATION_MIN": 0.08, "FAST_ALPHA": 0.30}),
        ("f078", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.78, "HAZARD_RISE_MIN": 0.12, "HAZARD_ACCELERATION_MIN": 0.08, "FAST_ALPHA": 0.30}),
        ("f079", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.79, "HAZARD_RISE_MIN": 0.12, "HAZARD_ACCELERATION_MIN": 0.08, "FAST_ALPHA": 0.30}),
        ("f080", {"BASELINE_BARS": 60, "EVENT_BODY_FRACTION_MIN": 0.80, "HAZARD_RISE_MIN": 0.12, "HAZARD_ACCELERATION_MIN": 0.08, "FAST_ALPHA": 0.30}),
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
            386, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
