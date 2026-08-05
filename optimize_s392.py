# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S392."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
    "latest": (2, "2026-07-30T00:00:00+07:00"),
}

GROUPS = {
    "information": (
        ("base", {}),
        ("info030", {"INFO_GAIN_MIN": 0.03}),
        ("info050", {"INFO_GAIN_MIN": 0.05}),
        ("info120", {"INFO_GAIN_MIN": 0.12}),
        ("info160", {"INFO_GAIN_MIN": 0.16}),
        ("rise000", {"INFO_GAIN_RISE_MIN": 0.00}),
        ("rise060", {"INFO_GAIN_RISE_MIN": 0.06}),
        ("rise100", {"INFO_GAIN_RISE_MIN": 0.10}),
        ("conf060", {"STATE_CONFIDENCE_MIN": 0.60}),
        ("conf070", {"STATE_CONFIDENCE_MIN": 0.70}),
        ("conf075", {"STATE_CONFIDENCE_MIN": 0.75}),
        ("support2", {"MIN_STATE_OBSERVATIONS": 2}),
        ("support4", {"MIN_STATE_OBSERVATIONS": 4}),
        ("q050", {"PRESSURE_QUANTILE": 0.50}),
        ("q065", {"PRESSURE_QUANTILE": 0.65}),
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
        ("baseline060", {"BASELINE_BARS": 60}),
        ("baseline100", {"BASELINE_BARS": 100}),
        ("recent020", {"RECENT_BARS": 20}),
        ("recent024", {"RECENT_BARS": 24}),
        ("recent032", {"RECENT_BARS": 32}),
        ("body045", {"EVENT_BODY_ATR_MIN": 0.45}),
        ("body065", {"EVENT_BODY_ATR_MIN": 0.65}),
        ("fraction055", {"EVENT_BODY_FRACTION_MIN": 0.55}),
        ("fraction075", {"EVENT_BODY_FRACTION_MIN": 0.75}),
        ("volume100", {"EVENT_VOLUME_RATIO_MIN": 1.00}),
        ("volume120", {"EVENT_VOLUME_RATIO_MIN": 1.20}),
    ),
    "focused": (
        ("conf075", {"STATE_CONFIDENCE_MIN": 0.75}),
        ("conf075_rr8", {"STATE_CONFIDENCE_MIN": 0.75, "TP_RR": 8.0}),
        ("conf075_rr9", {"STATE_CONFIDENCE_MIN": 0.75, "TP_RR": 9.0}),
        ("conf075_rr10", {"STATE_CONFIDENCE_MIN": 0.75, "TP_RR": 10.0}),
        ("conf075_support4", {"STATE_CONFIDENCE_MIN": 0.75, "MIN_STATE_OBSERVATIONS": 4}),
        ("conf075_q050", {"STATE_CONFIDENCE_MIN": 0.75, "PRESSURE_QUANTILE": 0.50}),
        ("conf075_info120", {"STATE_CONFIDENCE_MIN": 0.75, "INFO_GAIN_MIN": 0.12}),
        ("conf075_rise100", {"STATE_CONFIDENCE_MIN": 0.75, "INFO_GAIN_RISE_MIN": 0.10}),
    ),
    "final": (
        ("core", {"STATE_CONFIDENCE_MIN": 0.75, "TP_RR": 8.0}),
        ("support4", {"STATE_CONFIDENCE_MIN": 0.75, "TP_RR": 8.0, "MIN_STATE_OBSERVATIONS": 4}),
        ("conf072", {"STATE_CONFIDENCE_MIN": 0.72, "TP_RR": 8.0, "MIN_STATE_OBSERVATIONS": 4}),
        ("conf078", {"STATE_CONFIDENCE_MIN": 0.78, "TP_RR": 8.0, "MIN_STATE_OBSERVATIONS": 4}),
        ("conf080", {"STATE_CONFIDENCE_MIN": 0.80, "TP_RR": 8.0, "MIN_STATE_OBSERVATIONS": 4}),
        ("buy_only", {"STATE_CONFIDENCE_MIN": 0.75, "TP_RR": 8.0, "MIN_STATE_OBSERVATIONS": 4, "ALLOW_SELL": False}),
        ("sell_only", {"STATE_CONFIDENCE_MIN": 0.75, "TP_RR": 8.0, "MIN_STATE_OBSERVATIONS": 4, "ALLOW_BUY": False}),
        ("be001", {"STATE_CONFIDENCE_MIN": 0.75, "TP_RR": 8.0, "MIN_STATE_OBSERVATIONS": 4, "BE_RR": 0.01}),
        ("be005", {"STATE_CONFIDENCE_MIN": 0.75, "TP_RR": 8.0, "MIN_STATE_OBSERVATIONS": 4, "BE_RR": 0.05}),
        ("buffer016", {"STATE_CONFIDENCE_MIN": 0.75, "TP_RR": 8.0, "MIN_STATE_OBSERVATIONS": 4, "SL_BUFFER_ATR": 0.16}),
        ("buffer024", {"STATE_CONFIDENCE_MIN": 0.75, "TP_RR": 8.0, "MIN_STATE_OBSERVATIONS": 4, "SL_BUFFER_ATR": 0.24}),
    ),
    "polish": (
        ("buy_b020", {"STATE_CONFIDENCE_MIN": 0.75, "TP_RR": 8.0, "MIN_STATE_OBSERVATIONS": 4, "ALLOW_SELL": False, "SL_BUFFER_ATR": 0.20}),
        ("buy_b022", {"STATE_CONFIDENCE_MIN": 0.75, "TP_RR": 8.0, "MIN_STATE_OBSERVATIONS": 4, "ALLOW_SELL": False, "SL_BUFFER_ATR": 0.22}),
        ("buy_b024", {"STATE_CONFIDENCE_MIN": 0.75, "TP_RR": 8.0, "MIN_STATE_OBSERVATIONS": 4, "ALLOW_SELL": False, "SL_BUFFER_ATR": 0.24}),
        ("buy_b026", {"STATE_CONFIDENCE_MIN": 0.75, "TP_RR": 8.0, "MIN_STATE_OBSERVATIONS": 4, "ALLOW_SELL": False, "SL_BUFFER_ATR": 0.26}),
        ("buy_b028", {"STATE_CONFIDENCE_MIN": 0.75, "TP_RR": 8.0, "MIN_STATE_OBSERVATIONS": 4, "ALLOW_SELL": False, "SL_BUFFER_ATR": 0.28}),
        ("buy_rr7", {"STATE_CONFIDENCE_MIN": 0.75, "TP_RR": 7.0, "MIN_STATE_OBSERVATIONS": 4, "ALLOW_SELL": False}),
        ("buy_rr9", {"STATE_CONFIDENCE_MIN": 0.75, "TP_RR": 9.0, "MIN_STATE_OBSERVATIONS": 4, "ALLOW_SELL": False}),
        ("buy_rr10", {"STATE_CONFIDENCE_MIN": 0.75, "TP_RR": 10.0, "MIN_STATE_OBSERVATIONS": 4, "ALLOW_SELL": False}),
        ("buy_support5", {"STATE_CONFIDENCE_MIN": 0.75, "TP_RR": 8.0, "MIN_STATE_OBSERVATIONS": 5, "ALLOW_SELL": False}),
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
            392, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
