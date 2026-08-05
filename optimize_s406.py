# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S406."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
    "latest": (2, "2026-07-30T00:00:00+07:00"),
}

GROUPS = {
    "compression": (
        ("base", {}),
        ("nobreak", {"REQUIRE_CLOSE_BREAK": False}),
        ("ratio070", {"COMPRESSION_RATIO_MAX": 0.70}),
        ("ratio100", {"COMPRESSION_RATIO_MAX": 1.00}),
        ("drop000", {"COMPRESSION_DROP_ATR_MIN": 0.00}),
        ("drop050", {"COMPRESSION_DROP_ATR_MIN": 0.05}),
        ("release120", {"RELEASE_RANGE_RATIO_MIN": 1.20}),
        ("release180", {"RELEASE_RANGE_RATIO_MIN": 1.80}),
        ("recent020", {"BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("recent028", {"BASELINE_BARS": 84, "RECENT_BARS": 28}),
        ("session0715", {"SESSION_START_HOUR": 7}),
        ("session0915", {"SESSION_START_HOUR": 9}),
        ("session1318", {"SESSION_START_HOUR": 13, "SESSION_END_HOUR": 18}),
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
    "fade": (
        ("base", {"FADE_RELEASE": True}),
        ("nobreak", {"FADE_RELEASE": True, "REQUIRE_CLOSE_BREAK": False}),
        ("ratio070", {"FADE_RELEASE": True, "COMPRESSION_RATIO_MAX": 0.70}),
        ("ratio100", {"FADE_RELEASE": True, "COMPRESSION_RATIO_MAX": 1.00}),
        ("release120", {"FADE_RELEASE": True, "RELEASE_RANGE_RATIO_MIN": 1.20}),
        ("release180", {"FADE_RELEASE": True, "RELEASE_RANGE_RATIO_MIN": 1.80}),
        ("recent020", {"FADE_RELEASE": True, "BASELINE_BARS": 60,
                       "RECENT_BARS": 20}),
        ("recent028", {"FADE_RELEASE": True, "BASELINE_BARS": 84,
                       "RECENT_BARS": 28}),
        ("session0915", {"FADE_RELEASE": True, "SESSION_START_HOUR": 9}),
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
            406, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
