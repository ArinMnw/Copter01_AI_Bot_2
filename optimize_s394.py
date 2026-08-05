# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S394."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
    "latest": (2, "2026-07-30T00:00:00+07:00"),
}

GROUPS = {
    "variance_ratio": (
        ("base", {}),
        ("horizon2", {"VR_HORIZON": 2}),
        ("horizon3", {"VR_HORIZON": 3}),
        ("horizon5", {"VR_HORIZON": 5}),
        ("horizon6", {"VR_HORIZON": 6}),
        ("ratio100", {"VARIANCE_RATIO_MIN": 1.00}),
        ("ratio125", {"VARIANCE_RATIO_MIN": 1.25}),
        ("ratio140", {"VARIANCE_RATIO_MIN": 1.40}),
        ("rise000", {"VARIANCE_RATIO_RISE_MIN": 0.00}),
        ("rise200", {"VARIANCE_RATIO_RISE_MIN": 0.20}),
        ("rise300", {"VARIANCE_RATIO_RISE_MIN": 0.30}),
        ("baseline060", {"BASELINE_BARS": 60}),
        ("baseline100", {"BASELINE_BARS": 100}),
        ("recent020", {"RECENT_BARS": 20}),
        ("recent032", {"RECENT_BARS": 32}),
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
        ("net055", {"NET_MOVE_ATR_MIN": 0.55}),
        ("body055", {"EVENT_BODY_ATR_MIN": 0.55}),
        ("body075", {"EVENT_BODY_ATR_MIN": 0.75}),
        ("fraction068", {"EVENT_BODY_FRACTION_MIN": 0.68}),
        ("fraction078", {"EVENT_BODY_FRACTION_MIN": 0.78}),
        ("volume100", {"EVENT_VOLUME_RATIO_MIN": 1.00}),
        ("volume115", {"EVENT_VOLUME_RATIO_MIN": 1.15}),
    ),
    "focused": (
        ("core", {"VR_HORIZON": 3}),
        ("ratio100", {"VR_HORIZON": 3, "VARIANCE_RATIO_MIN": 1.00}),
        ("ratio125", {"VR_HORIZON": 3, "VARIANCE_RATIO_MIN": 1.25}),
        ("rise000", {"VR_HORIZON": 3, "VARIANCE_RATIO_RISE_MIN": 0.00}),
        ("rise200", {"VR_HORIZON": 3, "VARIANCE_RATIO_RISE_MIN": 0.20}),
        ("buy_only", {"VR_HORIZON": 3, "ALLOW_SELL": False}),
        ("sell_only", {"VR_HORIZON": 3, "ALLOW_BUY": False}),
        ("rr8", {"VR_HORIZON": 3, "TP_RR": 8.0}),
        ("rr9", {"VR_HORIZON": 3, "TP_RR": 9.0}),
        ("rr10", {"VR_HORIZON": 3, "TP_RR": 10.0}),
        ("be005", {"VR_HORIZON": 3, "BE_RR": 0.05}),
    ),
    "final": (
        ("rr10", {"VR_HORIZON": 3, "TP_RR": 10.0}),
        ("rr11", {"VR_HORIZON": 3, "TP_RR": 11.0}),
        ("rr12", {"VR_HORIZON": 3, "TP_RR": 12.0}),
        ("rr14", {"VR_HORIZON": 3, "TP_RR": 14.0}),
        ("sell_rr10", {"VR_HORIZON": 3, "TP_RR": 10.0, "ALLOW_BUY": False}),
        ("buffer016", {"VR_HORIZON": 3, "TP_RR": 10.0, "SL_BUFFER_ATR": 0.16}),
        ("buffer018", {"VR_HORIZON": 3, "TP_RR": 10.0, "SL_BUFFER_ATR": 0.18}),
        ("buffer021", {"VR_HORIZON": 3, "TP_RR": 10.0, "SL_BUFFER_ATR": 0.21}),
        ("buffer023", {"VR_HORIZON": 3, "TP_RR": 10.0, "SL_BUFFER_ATR": 0.23}),
    ),
    "polish": (
        ("b020", {"VR_HORIZON": 3, "TP_RR": 10.0, "SL_BUFFER_ATR": 0.20}),
        ("b021", {"VR_HORIZON": 3, "TP_RR": 10.0, "SL_BUFFER_ATR": 0.21}),
        ("b0215", {"VR_HORIZON": 3, "TP_RR": 10.0, "SL_BUFFER_ATR": 0.215}),
        ("b022", {"VR_HORIZON": 3, "TP_RR": 10.0, "SL_BUFFER_ATR": 0.22}),
        ("b0225", {"VR_HORIZON": 3, "TP_RR": 10.0, "SL_BUFFER_ATR": 0.225}),
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
            394, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
