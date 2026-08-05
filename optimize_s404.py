# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S404."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
    "latest": (2, "2026-07-30T00:00:00+07:00"),
}

GROUPS = {
    "impact": (
        ("base", {}),
        ("continuation", {"REQUIRE_REVERSAL": False}),
        ("ratio100", {"IMPACT_RATIO_MIN": 1.00}),
        ("ratio130", {"IMPACT_RATIO_MIN": 1.30}),
        ("ratio160", {"IMPACT_RATIO_MIN": 1.60}),
        ("rise000", {"IMPACT_RISE_ATR_MIN": 0.00}),
        ("rise030", {"IMPACT_RISE_ATR_MIN": 0.03}),
        ("signed000", {"SIGNED_IMPULSE_ATR_MIN": 0.00}),
        ("signed150", {"SIGNED_IMPULSE_ATR_MIN": 0.15}),
        ("quantile065", {"IMPACT_QUANTILE": 0.65}),
        ("quantile085", {"IMPACT_QUANTILE": 0.85}),
        ("recent020", {"BASELINE_BARS": 60, "RECENT_BARS": 20}),
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
    "quantile_local": (
        ("q060", {"IMPACT_QUANTILE": 0.60}),
        ("q062", {"IMPACT_QUANTILE": 0.62}),
        ("q064", {"IMPACT_QUANTILE": 0.64}),
        ("q065", {"IMPACT_QUANTILE": 0.65}),
        ("q066", {"IMPACT_QUANTILE": 0.66}),
        ("q068", {"IMPACT_QUANTILE": 0.68}),
        ("q070", {"IMPACT_QUANTILE": 0.70}),
    ),
    "buffer_local": (
        ("b016", {"SL_BUFFER_ATR": 0.16}),
        ("b018", {"SL_BUFFER_ATR": 0.18}),
        ("b020", {"SL_BUFFER_ATR": 0.20}),
        ("b022", {"SL_BUFFER_ATR": 0.22}),
        ("b024", {"SL_BUFFER_ATR": 0.24}),
        ("b026", {"SL_BUFFER_ATR": 0.26}),
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
            404, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
