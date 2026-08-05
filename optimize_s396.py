# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S396."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
    "latest": (2, "2026-07-30T00:00:00+07:00"),
}

GROUPS = {
    "buffer_local": (
        ("b014", {"SL_BUFFER_ATR": 0.14}),
        ("b015", {"SL_BUFFER_ATR": 0.15}),
        ("b016", {"SL_BUFFER_ATR": 0.16}),
        ("b017", {"SL_BUFFER_ATR": 0.17}),
        ("b018", {"SL_BUFFER_ATR": 0.18}),
        ("b019", {"SL_BUFFER_ATR": 0.19}),
        ("b020", {"SL_BUFFER_ATR": 0.20}),
    ),
    "allowance_extended": (
        ("a030", {"CUSUM_ALLOWANCE": 0.30}),
        ("a035", {"CUSUM_ALLOWANCE": 0.35}),
        ("a040", {"CUSUM_ALLOWANCE": 0.40}),
        ("a045", {"CUSUM_ALLOWANCE": 0.45}),
        ("a050", {"CUSUM_ALLOWANCE": 0.50}),
        ("a060", {"CUSUM_ALLOWANCE": 0.60}),
    ),
    "allowance_local": (
        ("a015", {"CUSUM_ALLOWANCE": 0.15}),
        ("a0175", {"CUSUM_ALLOWANCE": 0.175}),
        ("a020", {"CUSUM_ALLOWANCE": 0.20}),
        ("a0225", {"CUSUM_ALLOWANCE": 0.225}),
        ("a025", {"CUSUM_ALLOWANCE": 0.25}),
        ("a030", {"CUSUM_ALLOWANCE": 0.30}),
    ),
    "focused": (
        ("base", {}),
        ("allow020", {"CUSUM_ALLOWANCE": 0.20}),
        ("dom065", {"CUSUM_DOMINANCE_MIN": 0.65}),
        ("base060", {"BASELINE_BARS": 60}),
        ("allow_dom", {"CUSUM_ALLOWANCE": 0.20, "CUSUM_DOMINANCE_MIN": 0.65}),
        ("allow_base", {"CUSUM_ALLOWANCE": 0.20, "BASELINE_BARS": 60}),
        ("dom_base", {"CUSUM_DOMINANCE_MIN": 0.65, "BASELINE_BARS": 60}),
        ("all", {"CUSUM_ALLOWANCE": 0.20, "CUSUM_DOMINANCE_MIN": 0.65,
                 "BASELINE_BARS": 60}),
    ),
    "cusum": (
        ("base", {}),
        ("allow000", {"CUSUM_ALLOWANCE": 0.00}),
        ("allow020", {"CUSUM_ALLOWANCE": 0.20}),
        ("strength250", {"CUSUM_STRENGTH_MIN": 2.5}),
        ("strength550", {"CUSUM_STRENGTH_MIN": 5.5}),
        ("dominance025", {"CUSUM_DOMINANCE_MIN": 0.25}),
        ("dominance065", {"CUSUM_DOMINANCE_MIN": 0.65}),
        ("rise000", {"CUSUM_RISE_MIN": 0.00}),
        ("rise200", {"CUSUM_RISE_MIN": 2.00}),
        ("mean010", {"MEAN_SHIFT_Z_MIN": 0.10}),
        ("mean030", {"MEAN_SHIFT_Z_MIN": 0.30}),
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
        ("rr11", {"TP_RR": 11.0}),
        ("be005", {"BE_RR": 0.05}),
        ("be010", {"BE_RR": 0.10}),
        ("buffer016", {"SL_BUFFER_ATR": 0.16}),
        ("buffer024", {"SL_BUFFER_ATR": 0.24}),
    ),
    "breadth": (
        ("base", {}),
        ("path010", {"PATH_EFFICIENCY_MIN": 0.10}),
        ("path025", {"PATH_EFFICIENCY_MIN": 0.25}),
        ("net020", {"NET_MOVE_ATR_MIN": 0.20}),
        ("net050", {"NET_MOVE_ATR_MIN": 0.50}),
        ("volume100", {"EVENT_VOLUME_RATIO_MIN": 1.00}),
        ("volume115", {"EVENT_VOLUME_RATIO_MIN": 1.15}),
        ("body055", {"EVENT_BODY_ATR_MIN": 0.55}),
        ("body075", {"EVENT_BODY_ATR_MIN": 0.75}),
        ("fraction068", {"EVENT_BODY_FRACTION_MIN": 0.68}),
        ("fraction078", {"EVENT_BODY_FRACTION_MIN": 0.78}),
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
            396, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
