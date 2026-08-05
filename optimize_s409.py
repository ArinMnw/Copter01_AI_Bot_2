# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S409."""

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
        ("fade", {"FOLLOW_THROUGH": False}),
        ("noalign", {"REQUIRE_PATH_ALIGNMENT": False}),
        ("corr010", {"CORR_ABS_MIN": 0.10}),
        ("corr025", {"CORR_ABS_MIN": 0.25}),
        ("ratio100", {"CORR_RATIO_MIN": 1.00}),
        ("ratio150", {"CORR_RATIO_MIN": 1.50}),
        ("rise000", {"CORR_RISE_MIN": 0.00}),
        ("rise010", {"CORR_RISE_MIN": 0.10}),
        ("bias000", {"GAP_BIAS_FRACTION_MIN": 0.00}),
        ("bias015", {"GAP_BIAS_FRACTION_MIN": 0.15}),
        ("path006", {"PATH_EFFICIENCY_MIN": 0.06}),
        ("path020", {"PATH_EFFICIENCY_MIN": 0.20}),
        ("recent020", {"BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("recent028", {"BASELINE_BARS": 84, "RECENT_BARS": 28}),
        ("session0715", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15}),
        ("session1318", {"SESSION_START_HOUR": 13, "SESSION_END_HOUR": 18}),
    ),
    "finalists": (
        ("base", {}),
        ("fade", {"FOLLOW_THROUGH": False}),
        ("noalign", {"REQUIRE_PATH_ALIGNMENT": False}),
        ("corr025", {"CORR_ABS_MIN": 0.25}),
        ("bias015", {"GAP_BIAS_FRACTION_MIN": 0.15}),
        ("recent020", {"BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("session0715", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15}),
    ),
    "payoff_asian": (
        ("base", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15}),
        ("buy_only", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                      "ALLOW_SELL": False}),
        ("sell_only", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                       "ALLOW_BUY": False}),
        ("rr8", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                 "TP_RR": 8.0}),
        ("rr9", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                 "TP_RR": 9.0}),
        ("rr10", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                  "TP_RR": 10.0}),
        ("be005", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                   "BE_RR": 0.05}),
        ("be010", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                   "BE_RR": 0.10}),
        ("buffer014", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                       "SL_BUFFER_ATR": 0.14}),
        ("buffer022", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                       "SL_BUFFER_ATR": 0.22}),
    ),
    "event_asian": (
        ("base", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15}),
        ("volume080", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                       "EVENT_VOLUME_RATIO_MIN": 0.80}),
        ("volume120", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                       "EVENT_VOLUME_RATIO_MIN": 1.20}),
        ("body030", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                     "EVENT_BODY_ATR_MIN": 0.30}),
        ("body060", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                     "EVENT_BODY_ATR_MIN": 0.60}),
        ("fraction050", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                         "EVENT_BODY_FRACTION_MIN": 0.50}),
        ("fraction070", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                         "EVENT_BODY_FRACTION_MIN": 0.70}),
        ("close065", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                      "EVENT_CLOSE_FRACTION": 0.65}),
        ("close078", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                      "EVENT_CLOSE_FRACTION": 0.78}),
        ("session0815", {"SESSION_START_HOUR": 8, "SESSION_END_HOUR": 15}),
        ("session0714", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 14}),
        ("session0615", {"SESSION_START_HOUR": 6, "SESSION_END_HOUR": 15}),
    ),
    "opt_finalists": (
        ("base", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15}),
        ("sell_only", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                       "ALLOW_BUY": False}),
        ("rr8", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                 "TP_RR": 8.0}),
        ("rr9", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                 "TP_RR": 9.0}),
        ("rr10", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                  "TP_RR": 10.0}),
        ("volume120", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                       "EVENT_VOLUME_RATIO_MIN": 1.20}),
        ("body060", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                     "EVENT_BODY_ATR_MIN": 0.60}),
        ("fraction070", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                         "EVENT_BODY_FRACTION_MIN": 0.70}),
        ("session0815", {"SESSION_START_HOUR": 8, "SESSION_END_HOUR": 15}),
    ),
    "rr_tune": (
        ("rr750", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                   "TP_RR": 7.50}),
        ("rr800", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                   "TP_RR": 8.00}),
        ("rr825", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                   "TP_RR": 8.25}),
        ("rr850", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                   "TP_RR": 8.50}),
        ("rr875", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                   "TP_RR": 8.75}),
        ("rr900", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15,
                   "TP_RR": 9.00}),
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
        summary, _ = backtest(409, months, "M5", 0.20, 0.01, end, 300,
                              cfg, prepared)
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
