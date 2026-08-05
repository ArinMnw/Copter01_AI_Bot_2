# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S387."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
    "latest": (2, "2026-07-30T00:00:00+07:00"),
}

GROUPS = {
    "markov": (
        ("base", {}),
        ("q055", {"TAIL_QUANTILE": 0.55}),
        ("q065", {"TAIL_QUANTILE": 0.65}),
        ("p11_025", {"RECENT_P11_MIN": 0.25}),
        ("p11_045", {"RECENT_P11_MIN": 0.45}),
        ("p11_055", {"RECENT_P11_MIN": 0.55}),
        ("rise005", {"P11_RISE_MIN": 0.05}),
        ("rise010", {"P11_RISE_MIN": 0.10}),
        ("rise020", {"P11_RISE_MIN": 0.20}),
        ("rise025", {"P11_RISE_MIN": 0.25}),
        ("alpha05", {"LAPLACE_ALPHA": 0.5}),
        ("alpha20", {"LAPLACE_ALPHA": 2.0}),
        ("events4", {"MIN_TAIL_EVENTS": 4}),
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
        ("baseline050", {"BASELINE_BARS": 50}),
        ("baseline070", {"BASELINE_BARS": 70}),
        ("baseline080", {"BASELINE_BARS": 80}),
        ("recent016", {"RECENT_BARS": 16}),
        ("recent024", {"RECENT_BARS": 24}),
        ("body055", {"EVENT_BODY_ATR_MIN": 0.55}),
        ("body075", {"EVENT_BODY_ATR_MIN": 0.75}),
        ("fraction072", {"EVENT_BODY_FRACTION_MIN": 0.72}),
        ("fraction078", {"EVENT_BODY_FRACTION_MIN": 0.78}),
        ("volume100", {"EVENT_VOLUME_RATIO_MIN": 1.00}),
        ("volume120", {"EVENT_VOLUME_RATIO_MIN": 1.20}),
    ),
    "focused": (
        ("sell", {"ALLOW_BUY": False}),
        ("sell_q055", {"ALLOW_BUY": False, "TAIL_QUANTILE": 0.55}),
        ("sell_q065", {"ALLOW_BUY": False, "TAIL_QUANTILE": 0.65}),
        ("sell_rise010", {"ALLOW_BUY": False, "P11_RISE_MIN": 0.10}),
        ("sell_rise020", {"ALLOW_BUY": False, "P11_RISE_MIN": 0.20}),
        ("sell_rise025", {"ALLOW_BUY": False, "P11_RISE_MIN": 0.25}),
        ("sell_dir025", {"ALLOW_BUY": False, "TAIL_DIRECTIONAL_VOLUME_MIN": 0.25}),
        ("sell_q065_dir025", {"ALLOW_BUY": False, "TAIL_QUANTILE": 0.65, "TAIL_DIRECTIONAL_VOLUME_MIN": 0.25}),
        ("sell_q065_rise010", {"ALLOW_BUY": False, "TAIL_QUANTILE": 0.65, "P11_RISE_MIN": 0.10}),
        ("sell_q065_rise020", {"ALLOW_BUY": False, "TAIL_QUANTILE": 0.65, "P11_RISE_MIN": 0.20}),
        ("sell_q065_dir025_rise010", {"ALLOW_BUY": False, "TAIL_QUANTILE": 0.65, "TAIL_DIRECTIONAL_VOLUME_MIN": 0.25, "P11_RISE_MIN": 0.10}),
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
            387, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
