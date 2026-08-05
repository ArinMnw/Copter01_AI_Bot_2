# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S393."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
    "latest": (2, "2026-07-30T00:00:00+07:00"),
}

GROUPS = {
    "semivariance": (
        ("base", {}),
        ("imbalance015", {"SEMIVARIANCE_IMBALANCE_MIN": 0.15}),
        ("imbalance035", {"SEMIVARIANCE_IMBALANCE_MIN": 0.35}),
        ("imbalance045", {"SEMIVARIANCE_IMBALANCE_MIN": 0.45}),
        ("rise005", {"SEMIVARIANCE_RISE_MIN": 0.05}),
        ("rise010", {"SEMIVARIANCE_RISE_MIN": 0.10}),
        ("rise025", {"SEMIVARIANCE_RISE_MIN": 0.25}),
        ("jump000", {"JUMP_RATIO_MIN": 0.00}),
        ("jump050", {"JUMP_RATIO_MIN": 0.05}),
        ("jump150", {"JUMP_RATIO_MIN": 0.15}),
        ("jump200", {"JUMP_RATIO_MIN": 0.20}),
        ("baseline060", {"BASELINE_BARS": 60}),
        ("baseline100", {"BASELINE_BARS": 100}),
        ("recent020", {"RECENT_BARS": 20}),
        ("recent028", {"RECENT_BARS": 28}),
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
        ("path010", {"PATH_EFFICIENCY_MIN": 0.10}),
        ("path025", {"PATH_EFFICIENCY_MIN": 0.25}),
        ("net025", {"NET_MOVE_ATR_MIN": 0.25}),
        ("net050", {"NET_MOVE_ATR_MIN": 0.50}),
        ("body055", {"EVENT_BODY_ATR_MIN": 0.55}),
        ("body075", {"EVENT_BODY_ATR_MIN": 0.75}),
        ("fraction068", {"EVENT_BODY_FRACTION_MIN": 0.68}),
        ("fraction078", {"EVENT_BODY_FRACTION_MIN": 0.78}),
        ("volume100", {"EVENT_VOLUME_RATIO_MIN": 1.00}),
        ("volume115", {"EVENT_VOLUME_RATIO_MIN": 1.15}),
    ),
    "focused": (
        ("core", {"JUMP_RATIO_MIN": 0.00}),
        ("imbalance035", {"JUMP_RATIO_MIN": 0.00, "SEMIVARIANCE_IMBALANCE_MIN": 0.35}),
        ("imbalance045", {"JUMP_RATIO_MIN": 0.00, "SEMIVARIANCE_IMBALANCE_MIN": 0.45}),
        ("imbalance055", {"JUMP_RATIO_MIN": 0.00, "SEMIVARIANCE_IMBALANCE_MIN": 0.55}),
        ("rise025", {"JUMP_RATIO_MIN": 0.00, "SEMIVARIANCE_RISE_MIN": 0.25}),
        ("rise035", {"JUMP_RATIO_MIN": 0.00, "SEMIVARIANCE_RISE_MIN": 0.35}),
        ("buy_only", {"JUMP_RATIO_MIN": 0.00, "ALLOW_SELL": False}),
        ("sell_only", {"JUMP_RATIO_MIN": 0.00, "ALLOW_BUY": False}),
        ("rr8", {"JUMP_RATIO_MIN": 0.00, "TP_RR": 8.0}),
        ("rr9", {"JUMP_RATIO_MIN": 0.00, "TP_RR": 9.0}),
        ("rr10", {"JUMP_RATIO_MIN": 0.00, "TP_RR": 10.0}),
    ),
    "final": (
        ("core", {"JUMP_RATIO_MIN": 0.00, "TP_RR": 9.0}),
        ("buffer016", {"JUMP_RATIO_MIN": 0.00, "TP_RR": 9.0, "SL_BUFFER_ATR": 0.16}),
        ("buffer018", {"JUMP_RATIO_MIN": 0.00, "TP_RR": 9.0, "SL_BUFFER_ATR": 0.18}),
        ("buffer022", {"JUMP_RATIO_MIN": 0.00, "TP_RR": 9.0, "SL_BUFFER_ATR": 0.22}),
        ("buffer024", {"JUMP_RATIO_MIN": 0.00, "TP_RR": 9.0, "SL_BUFFER_ATR": 0.24}),
        ("be001", {"JUMP_RATIO_MIN": 0.00, "TP_RR": 9.0, "BE_RR": 0.01}),
        ("be005", {"JUMP_RATIO_MIN": 0.00, "TP_RR": 9.0, "BE_RR": 0.05}),
        ("be010", {"JUMP_RATIO_MIN": 0.00, "TP_RR": 9.0, "BE_RR": 0.10}),
        ("baseline060", {"JUMP_RATIO_MIN": 0.00, "TP_RR": 9.0, "BASELINE_BARS": 60}),
        ("recent020", {"JUMP_RATIO_MIN": 0.00, "TP_RR": 9.0, "RECENT_BARS": 20}),
    ),
    "buffer_local": (
        ("b017", {"JUMP_RATIO_MIN": 0.00, "TP_RR": 9.0, "SL_BUFFER_ATR": 0.17}),
        ("b018", {"JUMP_RATIO_MIN": 0.00, "TP_RR": 9.0, "SL_BUFFER_ATR": 0.18}),
        ("b019", {"JUMP_RATIO_MIN": 0.00, "TP_RR": 9.0, "SL_BUFFER_ATR": 0.19}),
        ("b020", {"JUMP_RATIO_MIN": 0.00, "TP_RR": 9.0, "SL_BUFFER_ATR": 0.20}),
        ("b021", {"JUMP_RATIO_MIN": 0.00, "TP_RR": 9.0, "SL_BUFFER_ATR": 0.21}),
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
            393, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
