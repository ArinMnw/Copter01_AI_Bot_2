# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S395."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
    "latest": (2, "2026-07-30T00:00:00+07:00"),
}

GROUPS = {
    "fade": (
        ("fade7", {"FADE_SIGNAL": True}),
        ("fade8", {"FADE_SIGNAL": True, "TP_RR": 8.0}),
        ("fade10", {"FADE_SIGNAL": True, "TP_RR": 10.0}),
        ("fade_be005", {"FADE_SIGNAL": True, "BE_RR": 0.05}),
    ),
    "spectral": (
        ("base", {}),
        ("bins5", {"SPECTRAL_BINS": 5}),
        ("bins6", {"SPECTRAL_BINS": 6}),
        ("bins10", {"SPECTRAL_BINS": 10}),
        ("low1", {"LOW_FREQUENCY_BINS": 1}),
        ("low3", {"LOW_FREQUENCY_BINS": 3}),
        ("entropy080", {"SPECTRAL_ENTROPY_MAX": 0.80}),
        ("entropy092", {"SPECTRAL_ENTROPY_MAX": 0.92}),
        ("drop000", {"ENTROPY_DROP_MIN": 0.00}),
        ("drop060", {"ENTROPY_DROP_MIN": 0.06}),
        ("share030", {"LOW_FREQUENCY_SHARE_MIN": 0.30}),
        ("share046", {"LOW_FREQUENCY_SHARE_MIN": 0.46}),
        ("rise000", {"LOW_FREQUENCY_RISE_MIN": 0.00}),
        ("rise080", {"LOW_FREQUENCY_RISE_MIN": 0.08}),
    ),
    "windows": (
        ("base", {}),
        ("base056", {"BASELINE_BARS": 56}),
        ("base112", {"BASELINE_BARS": 112}),
        ("recent020", {"BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("recent024", {"BASELINE_BARS": 72, "RECENT_BARS": 24}),
        ("recent032", {"BASELINE_BARS": 96, "RECENT_BARS": 32}),
        ("path010", {"PATH_EFFICIENCY_MIN": 0.10}),
        ("path025", {"PATH_EFFICIENCY_MIN": 0.25}),
        ("net025", {"NET_MOVE_ATR_MIN": 0.25}),
        ("net055", {"NET_MOVE_ATR_MIN": 0.55}),
    ),
    "payoff": (
        ("base", {}),
        ("fade", {"FADE_SIGNAL": True}),
        ("fade_rr8", {"FADE_SIGNAL": True, "TP_RR": 8.0}),
        ("fade_rr10", {"FADE_SIGNAL": True, "TP_RR": 10.0}),
        ("fade_be005", {"FADE_SIGNAL": True, "BE_RR": 0.05}),
        ("buy_only", {"ALLOW_SELL": False}),
        ("sell_only", {"ALLOW_BUY": False}),
        ("rr8", {"TP_RR": 8.0}),
        ("rr9", {"TP_RR": 9.0}),
        ("rr10", {"TP_RR": 10.0}),
        ("rr11", {"TP_RR": 11.0}),
        ("be005", {"BE_RR": 0.05}),
        ("be010", {"BE_RR": 0.10}),
        ("buffer016", {"SL_BUFFER_ATR": 0.16}),
        ("buffer024", {"SL_BUFFER_ATR": 0.24}),
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
            395, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
