# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S399."""

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
        ("b018", {"SL_BUFFER_ATR": 0.18}),
        ("b019", {"SL_BUFFER_ATR": 0.19}),
        ("b020", {"SL_BUFFER_ATR": 0.20}),
        ("b021", {"SL_BUFFER_ATR": 0.21}),
        ("b022", {"SL_BUFFER_ATR": 0.22}),
        ("b023", {"SL_BUFFER_ATR": 0.23}),
        ("b024", {"SL_BUFFER_ATR": 0.24}),
    ),
    "local": (
        ("r026_e000", {"BASELINE_BARS": 78, "RECENT_BARS": 26,
                       "L_KURTOSIS_RISE_MIN": 0.00}),
        ("r027_e000", {"BASELINE_BARS": 81, "RECENT_BARS": 27,
                       "L_KURTOSIS_RISE_MIN": 0.00}),
        ("r028_e000", {"BASELINE_BARS": 84, "RECENT_BARS": 28,
                       "L_KURTOSIS_RISE_MIN": 0.00}),
        ("r029_e000", {"BASELINE_BARS": 87, "RECENT_BARS": 29,
                       "L_KURTOSIS_RISE_MIN": 0.00}),
        ("r030_e000", {"BASELINE_BARS": 90, "RECENT_BARS": 30,
                       "L_KURTOSIS_RISE_MIN": 0.00}),
        ("r028_e010", {"BASELINE_BARS": 84, "RECENT_BARS": 28,
                       "L_KURTOSIS_RISE_MIN": 0.01}),
        ("r028_e020", {"BASELINE_BARS": 84, "RECENT_BARS": 28,
                       "L_KURTOSIS_RISE_MIN": 0.02}),
        ("r028_e030", {"BASELINE_BARS": 84, "RECENT_BARS": 28,
                       "L_KURTOSIS_RISE_MIN": 0.03}),
        ("r028_e040", {"BASELINE_BARS": 84, "RECENT_BARS": 28,
                       "L_KURTOSIS_RISE_MIN": 0.04}),
    ),
    "focused": (
        ("base", {}),
        ("rise000", {"L_KURTOSIS_RISE_MIN": 0.00}),
        ("rise008", {"L_KURTOSIS_RISE_MIN": 0.08}),
        ("rise014", {"L_KURTOSIS_RISE_MIN": 0.14}),
        ("kurt022", {"L_KURTOSIS_MIN": 0.22}),
        ("recent028", {"BASELINE_BARS": 84, "RECENT_BARS": 28}),
        ("recent032", {"BASELINE_BARS": 96, "RECENT_BARS": 32}),
        ("r028_rise0", {"BASELINE_BARS": 84, "RECENT_BARS": 28,
                        "L_KURTOSIS_RISE_MIN": 0.00}),
    ),
    "l_kurtosis": (
        ("base", {}),
        ("kurt000", {"L_KURTOSIS_MIN": 0.00}),
        ("kurt016", {"L_KURTOSIS_MIN": 0.16}),
        ("kurt022", {"L_KURTOSIS_MIN": 0.22}),
        ("rise000", {"L_KURTOSIS_RISE_MIN": 0.00}),
        ("rise008", {"L_KURTOSIS_RISE_MIN": 0.08}),
        ("rise014", {"L_KURTOSIS_RISE_MIN": 0.14}),
        ("scale000", {"L_SCALE_ATR_MIN": 0.00}),
        ("scale014", {"L_SCALE_ATR_MIN": 0.14}),
        ("baseline048", {"BASELINE_BARS": 48}),
        ("baseline096", {"BASELINE_BARS": 96}),
        ("recent020", {"BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("recent028", {"BASELINE_BARS": 84, "RECENT_BARS": 28}),
        ("recent032", {"BASELINE_BARS": 96, "RECENT_BARS": 32}),
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
            399, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
