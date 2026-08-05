# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S405."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
    "latest": (2, "2026-07-30T00:00:00+07:00"),
}

GROUPS = {
    "vr": (
        ("base", {}),
        ("continuation", {"REQUIRE_REVERSAL": False}),
        ("vrmax080", {"VR_MAX": 0.80}),
        ("vrmax110", {"VR_MAX": 1.10}),
        ("ratio100", {"VR_BASELINE_RATIO_MIN": 1.00}),
        ("ratio120", {"VR_BASELINE_RATIO_MIN": 1.20}),
        ("drop000", {"VR_DROP_MIN": 0.00}),
        ("drop080", {"VR_DROP_MIN": 0.08}),
        ("horizon3", {"VR_HORIZON": 3}),
        ("horizon5", {"VR_HORIZON": 5}),
        ("recent024", {"BASELINE_BARS": 72, "RECENT_BARS": 24}),
        ("recent028", {"BASELINE_BARS": 84, "RECENT_BARS": 28}),
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
    "focused": (
        ("base", {}),
        ("vrmax080", {"VR_MAX": 0.80}),
        ("vrmax110", {"VR_MAX": 1.10}),
        ("ratio100", {"VR_BASELINE_RATIO_MIN": 1.00}),
        ("ratio120", {"VR_BASELINE_RATIO_MIN": 1.20}),
        ("drop000", {"VR_DROP_MIN": 0.00}),
        ("drop080", {"VR_DROP_MIN": 0.08}),
        ("horizon3", {"VR_HORIZON": 3}),
        ("horizon5", {"VR_HORIZON": 5}),
        ("move040", {"NET_MOVE_ATR_MIN": 0.40}),
    ),
    "drop_local": (
        ("d004", {"VR_DROP_MIN": 0.04}),
        ("d006", {"VR_DROP_MIN": 0.06}),
        ("d008", {"VR_DROP_MIN": 0.08}),
        ("d010", {"VR_DROP_MIN": 0.10}),
        ("d012", {"VR_DROP_MIN": 0.12}),
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
            405, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
