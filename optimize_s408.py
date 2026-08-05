# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S408."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
    "latest": (2, "2026-07-30T00:00:00+07:00"),
}

GROUPS = {
    "structure": (
        ("base", {}),
        ("fade", {"FADE_DISLOCATION": True}),
        ("share000", {"GAP_SHARE_MIN": 0.0}),
        ("share005", {"GAP_SHARE_MIN": 0.0005}),
        ("ratio100", {"GAP_SHARE_RATIO_MIN": 1.00}),
        ("ratio150", {"GAP_SHARE_RATIO_MIN": 1.50}),
        ("rise000", {"GAP_SHARE_RISE_MIN": 0.0}),
        ("rise001", {"GAP_SHARE_RISE_MIN": 0.0001}),
        ("energy000", {"GAP_ENERGY_MIN": 0.0}),
        ("energy005", {"GAP_ENERGY_MIN": 0.00000001}),
        ("path006", {"PATH_EFFICIENCY_MIN": 0.06}),
        ("path020", {"PATH_EFFICIENCY_MIN": 0.20}),
        ("recent020", {"BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("recent028", {"BASELINE_BARS": 84, "RECENT_BARS": 28}),
        ("session0715", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15}),
        ("session1318", {"SESSION_START_HOUR": 13, "SESSION_END_HOUR": 18}),
    ),
    "finalists": (
        ("base", {}),
        ("fade", {"FADE_DISLOCATION": True}),
        ("share005", {"GAP_SHARE_MIN": 0.0005}),
        ("ratio150", {"GAP_SHARE_RATIO_MIN": 1.50}),
        ("path020", {"PATH_EFFICIENCY_MIN": 0.20}),
        ("session0715", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15}),
        ("session0715_path020", {"SESSION_START_HOUR": 7,
                                 "SESSION_END_HOUR": 15,
                                 "PATH_EFFICIENCY_MIN": 0.20}),
    ),
    "payoff": (
        ("base", {}),
        ("buy_only", {"ALLOW_SELL": False}),
        ("sell_only", {"ALLOW_BUY": False}),
        ("rr8", {"TP_RR": 8.0}),
        ("rr9", {"TP_RR": 9.0}),
        ("rr10", {"TP_RR": 10.0}),
        ("be005", {"BE_RR": 0.05}),
        ("be010", {"BE_RR": 0.10}),
        ("buffer014", {"SL_BUFFER_ATR": 0.14}),
        ("buffer022", {"SL_BUFFER_ATR": 0.22}),
        ("risk125", {"MAX_RISK_ATR": 1.25}),
        ("risk150", {"MAX_RISK_ATR": 1.50}),
    ),
    "event": (
        ("base", {}),
        ("volume080", {"EVENT_VOLUME_RATIO_MIN": 0.80}),
        ("volume120", {"EVENT_VOLUME_RATIO_MIN": 1.20}),
        ("body030", {"EVENT_BODY_ATR_MIN": 0.30}),
        ("body060", {"EVENT_BODY_ATR_MIN": 0.60}),
        ("range050", {"EVENT_RANGE_ATR_MIN": 0.50}),
        ("range080", {"EVENT_RANGE_ATR_MIN": 0.80}),
        ("fraction050", {"EVENT_BODY_FRACTION_MIN": 0.50}),
        ("fraction070", {"EVENT_BODY_FRACTION_MIN": 0.70}),
        ("close060", {"EVENT_CLOSE_FRACTION": 0.60}),
        ("close075", {"EVENT_CLOSE_FRACTION": 0.75}),
        ("session1423", {"SESSION_START_HOUR": 14}),
        ("session1623", {"SESSION_START_HOUR": 16}),
    ),
    "opt_finalists": (
        ("base", {}),
        ("buy_only", {"ALLOW_SELL": False}),
        ("rr8", {"TP_RR": 8.0}),
        ("rr9", {"TP_RR": 9.0}),
        ("rr10", {"TP_RR": 10.0}),
        ("buffer022", {"SL_BUFFER_ATR": 0.22}),
        ("body060", {"EVENT_BODY_ATR_MIN": 0.60}),
        ("fraction070", {"EVENT_BODY_FRACTION_MIN": 0.70}),
        ("close075", {"EVENT_CLOSE_FRACTION": 0.75}),
    ),
    "close_tune": (
        ("close070", {"EVENT_CLOSE_FRACTION": 0.70}),
        ("close072", {"EVENT_CLOSE_FRACTION": 0.72}),
        ("close075", {"EVENT_CLOSE_FRACTION": 0.75}),
        ("close078", {"EVENT_CLOSE_FRACTION": 0.78}),
        ("close080", {"EVENT_CLOSE_FRACTION": 0.80}),
        ("close075_body060", {"EVENT_CLOSE_FRACTION": 0.75,
                              "EVENT_BODY_ATR_MIN": 0.60}),
        ("close075_share005", {"EVENT_CLOSE_FRACTION": 0.75,
                               "GAP_SHARE_MIN": 0.0005}),
        ("close075_path020", {"EVENT_CLOSE_FRACTION": 0.75,
                              "PATH_EFFICIENCY_MIN": 0.20}),
    ),
}


def _view(summary):
    return {key: summary[key] for key in (
        "closed", "wins", "win_rate", "net_profit",
        "profit_factor", "max_drawdown",
    )}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", choices=tuple(WINDOWS), required=True)
    parser.add_argument("--group", choices=tuple(GROUPS), required=True)
    args = parser.parse_args()
    months, end_text = WINDOWS[args.window]
    end = parse_bkk(end_text)
    prepared = prepare_rates(months, "M5", end, 300)
    for name, cfg in GROUPS[args.group]:
        summary, _ = backtest(408, months, "M5", 0.20, 0.01, end, 300,
                              cfg, prepared)
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
