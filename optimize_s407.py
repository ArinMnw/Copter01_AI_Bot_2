# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S407."""

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
        ("noreentry", {"REQUIRE_RANGE_REENTRY": False}),
        ("continuation", {"FADE_EXCURSION": False,
                          "REQUIRE_RANGE_REENTRY": False}),
        ("ratio100", {"SPREAD_RATIO_MIN": 1.00}),
        ("ratio150", {"SPREAD_RATIO_MIN": 1.50}),
        ("rise000", {"SPREAD_RISE_MIN": 0.0}),
        ("rise005", {"SPREAD_RISE_MIN": 0.00005}),
        ("quantile060", {"SPREAD_QUANTILE": 0.60}),
        ("quantile080", {"SPREAD_QUANTILE": 0.80}),
        ("path006", {"PATH_EFFICIENCY_MIN": 0.06}),
        ("path020", {"PATH_EFFICIENCY_MIN": 0.20}),
        ("recent020", {"BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("recent028", {"BASELINE_BARS": 84, "RECENT_BARS": 28}),
        ("session0715", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15}),
        ("session1318", {"SESSION_START_HOUR": 13, "SESSION_END_HOUR": 18}),
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
    ),
    "continuation": (
        ("base", {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False}),
        ("ratio100", {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False,
                      "SPREAD_RATIO_MIN": 1.00}),
        ("ratio150", {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False,
                      "SPREAD_RATIO_MIN": 1.50}),
        ("quantile060", {"FADE_EXCURSION": False,
                         "REQUIRE_RANGE_REENTRY": False,
                         "SPREAD_QUANTILE": 0.60}),
        ("quantile080", {"FADE_EXCURSION": False,
                         "REQUIRE_RANGE_REENTRY": False,
                         "SPREAD_QUANTILE": 0.80}),
        ("path006", {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False,
                     "PATH_EFFICIENCY_MIN": 0.06}),
        ("path020", {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False,
                     "PATH_EFFICIENCY_MIN": 0.20}),
        ("net020", {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False,
                    "NET_MOVE_ATR_MIN": 0.20}),
        ("net060", {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False,
                    "NET_MOVE_ATR_MIN": 0.60}),
        ("recent020", {"FADE_EXCURSION": False,
                       "REQUIRE_RANGE_REENTRY": False,
                       "BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("recent028", {"FADE_EXCURSION": False,
                       "REQUIRE_RANGE_REENTRY": False,
                       "BASELINE_BARS": 84, "RECENT_BARS": 28}),
        ("session1318", {"FADE_EXCURSION": False,
                         "REQUIRE_RANGE_REENTRY": False,
                         "SESSION_START_HOUR": 13, "SESSION_END_HOUR": 18}),
    ),
    "payoff_cont": (
        ("base", {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False}),
        ("buy_only", {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False,
                      "ALLOW_SELL": False}),
        ("sell_only", {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False,
                       "ALLOW_BUY": False}),
        ("rr8", {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False,
                 "TP_RR": 8.0}),
        ("rr9", {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False,
                 "TP_RR": 9.0}),
        ("rr10", {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False,
                  "TP_RR": 10.0}),
        ("be005", {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False,
                   "BE_RR": 0.05}),
        ("be010", {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False,
                   "BE_RR": 0.10}),
        ("buffer014", {"FADE_EXCURSION": False,
                       "REQUIRE_RANGE_REENTRY": False,
                       "SL_BUFFER_ATR": 0.14}),
        ("buffer022", {"FADE_EXCURSION": False,
                       "REQUIRE_RANGE_REENTRY": False,
                       "SL_BUFFER_ATR": 0.22}),
    ),
    "event_cont": (
        ("base", {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False}),
        ("volume080", {"FADE_EXCURSION": False,
                       "REQUIRE_RANGE_REENTRY": False,
                       "EVENT_VOLUME_RATIO_MIN": 0.80}),
        ("volume120", {"FADE_EXCURSION": False,
                       "REQUIRE_RANGE_REENTRY": False,
                       "EVENT_VOLUME_RATIO_MIN": 1.20}),
        ("body030", {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False,
                     "EVENT_BODY_ATR_MIN": 0.30}),
        ("body060", {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False,
                     "EVENT_BODY_ATR_MIN": 0.60}),
        ("range050", {"FADE_EXCURSION": False,
                      "REQUIRE_RANGE_REENTRY": False,
                      "EVENT_RANGE_ATR_MIN": 0.50}),
        ("range080", {"FADE_EXCURSION": False,
                      "REQUIRE_RANGE_REENTRY": False,
                      "EVENT_RANGE_ATR_MIN": 0.80}),
        ("fraction045", {"FADE_EXCURSION": False,
                         "REQUIRE_RANGE_REENTRY": False,
                         "EVENT_BODY_FRACTION_MIN": 0.45}),
        ("fraction070", {"FADE_EXCURSION": False,
                         "REQUIRE_RANGE_REENTRY": False,
                         "EVENT_BODY_FRACTION_MIN": 0.70}),
        ("close060", {"FADE_EXCURSION": False,
                      "REQUIRE_RANGE_REENTRY": False,
                      "EVENT_CLOSE_FRACTION": 0.60}),
        ("close075", {"FADE_EXCURSION": False,
                      "REQUIRE_RANGE_REENTRY": False,
                      "EVENT_CLOSE_FRACTION": 0.75}),
        ("session1423", {"FADE_EXCURSION": False,
                         "REQUIRE_RANGE_REENTRY": False,
                         "SESSION_START_HOUR": 14}),
        ("session1522", {"FADE_EXCURSION": False,
                         "REQUIRE_RANGE_REENTRY": False,
                         "SESSION_END_HOUR": 22}),
        ("session1623", {"FADE_EXCURSION": False,
                         "REQUIRE_RANGE_REENTRY": False,
                         "SESSION_START_HOUR": 16}),
        ("risk125", {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False,
                     "MAX_RISK_ATR": 1.25}),
        ("risk150", {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False,
                     "MAX_RISK_ATR": 1.50}),
    ),
    "event_finalists": (
        ("base", {"FADE_EXCURSION": False, "REQUIRE_RANGE_REENTRY": False}),
        ("body060", {"FADE_EXCURSION": False,
                     "REQUIRE_RANGE_REENTRY": False,
                     "EVENT_BODY_ATR_MIN": 0.60}),
        ("fraction070", {"FADE_EXCURSION": False,
                         "REQUIRE_RANGE_REENTRY": False,
                         "EVENT_BODY_FRACTION_MIN": 0.70}),
        ("risk125", {"FADE_EXCURSION": False,
                     "REQUIRE_RANGE_REENTRY": False,
                     "MAX_RISK_ATR": 1.25}),
        ("risk150", {"FADE_EXCURSION": False,
                     "REQUIRE_RANGE_REENTRY": False,
                     "MAX_RISK_ATR": 1.50}),
        ("body060_risk150", {"FADE_EXCURSION": False,
                             "REQUIRE_RANGE_REENTRY": False,
                             "EVENT_BODY_ATR_MIN": 0.60,
                             "MAX_RISK_ATR": 1.50}),
        ("fraction070_risk150", {"FADE_EXCURSION": False,
                                 "REQUIRE_RANGE_REENTRY": False,
                                 "EVENT_BODY_FRACTION_MIN": 0.70,
                                 "MAX_RISK_ATR": 1.50}),
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
        summary, _ = backtest(407, months, "M5", 0.20, 0.01, end, 300,
                              cfg, prepared)
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
