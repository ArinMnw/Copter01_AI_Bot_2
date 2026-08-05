# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S380."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
}

GROUPS = {
    "buffer_local": tuple(
        (
            f"buffer{int(buffer * 100):03d}",
            {
                "TREND_EXPANSION_MIN": 0.80,
                "EVENT_BODY_FRACTION_MIN": 0.70,
                "TP_RR": 12.0,
                "BE_RR": 0.02,
                "SL_BUFFER_ATR": buffer,
            },
        )
        for buffer in (0.12, 0.14, 0.16, 0.18, 0.20)
    ),
    "risk": (
        (
            "final",
            {
                "TREND_EXPANSION_MIN": 0.80,
                "EVENT_BODY_FRACTION_MIN": 0.70,
                "TP_RR": 12.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "be001",
            {
                "TREND_EXPANSION_MIN": 0.80,
                "EVENT_BODY_FRACTION_MIN": 0.70,
                "TP_RR": 12.0,
                "BE_RR": 0.01,
            },
        ),
        (
            "buffer004",
            {
                "TREND_EXPANSION_MIN": 0.80,
                "EVENT_BODY_FRACTION_MIN": 0.70,
                "TP_RR": 12.0,
                "BE_RR": 0.02,
                "SL_BUFFER_ATR": 0.04,
            },
        ),
        (
            "buffer012",
            {
                "TREND_EXPANSION_MIN": 0.80,
                "EVENT_BODY_FRACTION_MIN": 0.70,
                "TP_RR": 12.0,
                "BE_RR": 0.02,
                "SL_BUFFER_ATR": 0.12,
            },
        ),
        (
            "buffer016",
            {
                "TREND_EXPANSION_MIN": 0.80,
                "EVENT_BODY_FRACTION_MIN": 0.70,
                "TP_RR": 12.0,
                "BE_RR": 0.02,
                "SL_BUFFER_ATR": 0.16,
            },
        ),
        (
            "buffer020",
            {
                "TREND_EXPANSION_MIN": 0.80,
                "EVENT_BODY_FRACTION_MIN": 0.70,
                "TP_RR": 12.0,
                "BE_RR": 0.02,
                "SL_BUFFER_ATR": 0.20,
            },
        ),
    ),
    "rr_extreme": tuple(
        (
            f"rr{int(rr):02d}",
            {
                "TREND_EXPANSION_MIN": 0.80,
                "EVENT_BODY_FRACTION_MIN": 0.70,
                "TP_RR": rr,
                "BE_RR": 0.02,
            },
        )
        for rr in (12.0, 13.0, 14.0, 15.0, 16.0)
    ),
    "rr_tail": tuple(
        (
            f"rr{int(rr):02d}",
            {
                "TREND_EXPANSION_MIN": 0.80,
                "EVENT_BODY_FRACTION_MIN": 0.70,
                "TP_RR": rr,
                "BE_RR": 0.02,
            },
        )
        for rr in (9.0, 10.0, 11.0, 12.0, 13.0)
    ),
    "interaction": (
        ("base", {}),
        (
            "trend_event",
            {
                "TREND_EXPANSION_MIN": 0.80,
                "EVENT_BODY_FRACTION_MIN": 0.70,
            },
        ),
        (
            "all",
            {
                "TREND_EXPANSION_MIN": 0.80,
                "EVENT_BODY_FRACTION_MIN": 0.70,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "all_rr8",
            {
                "TREND_EXPANSION_MIN": 0.80,
                "EVENT_BODY_FRACTION_MIN": 0.70,
                "TP_RR": 8.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "all_rr10",
            {
                "TREND_EXPANSION_MIN": 0.80,
                "EVENT_BODY_FRACTION_MIN": 0.70,
                "TP_RR": 10.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "all_be001",
            {
                "TREND_EXPANSION_MIN": 0.80,
                "EVENT_BODY_FRACTION_MIN": 0.70,
                "TP_RR": 9.0,
                "BE_RR": 0.01,
            },
        ),
        (
            "all_close080",
            {
                "TREND_EXPANSION_MIN": 0.80,
                "EVENT_BODY_FRACTION_MIN": 0.70,
                "EVENT_CLOSE_FRACTION": 0.80,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "all_exp060",
            {
                "TREND_EXPANSION_MIN": 0.60,
                "EVENT_BODY_FRACTION_MIN": 0.70,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "all_exp100",
            {
                "TREND_EXPANSION_MIN": 1.00,
                "EVENT_BODY_FRACTION_MIN": 0.70,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "all_fraction065",
            {
                "TREND_EXPANSION_MIN": 0.80,
                "EVENT_BODY_FRACTION_MIN": 0.65,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "all_fraction075",
            {
                "TREND_EXPANSION_MIN": 0.80,
                "EVENT_BODY_FRACTION_MIN": 0.75,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
            },
        ),
    ),
    "payoff": (
        ("base", {}),
        ("buy_only", {"ALLOW_SELL": False}),
        ("sell_only", {"ALLOW_BUY": False}),
        ("rr8", {"TP_RR": 8.0}),
        ("rr9", {"TP_RR": 9.0}),
        ("rr10", {"TP_RR": 10.0}),
        ("be001", {"BE_RR": 0.01}),
        ("be002", {"BE_RR": 0.02}),
        ("be008", {"BE_RR": 0.08}),
        ("be012", {"BE_RR": 0.12}),
    ),
    "trend": (
        ("base", {}),
        ("z060", {"TREND_Z_MIN": 0.60}),
        ("z080", {"TREND_Z_MIN": 0.80}),
        ("z120", {"TREND_Z_MIN": 1.20}),
        ("z150", {"TREND_Z_MIN": 1.50}),
        ("expansion010", {"TREND_EXPANSION_MIN": 0.10}),
        ("expansion050", {"TREND_EXPANSION_MIN": 0.50}),
        ("expansion080", {"TREND_EXPANSION_MIN": 0.80}),
        ("path015", {"PATH_EFFICIENCY_MIN": 0.15}),
        ("path035", {"PATH_EFFICIENCY_MIN": 0.35}),
        ("net025", {"NET_MOVE_ATR_MIN": 0.25}),
        ("net065", {"NET_MOVE_ATR_MIN": 0.65}),
    ),
    "event": (
        ("base", {}),
        ("body035", {"EVENT_BODY_ATR_MIN": 0.35}),
        ("body065", {"EVENT_BODY_ATR_MIN": 0.65}),
        ("body080", {"EVENT_BODY_ATR_MIN": 0.80}),
        ("range060", {"EVENT_RANGE_ATR_MIN": 0.60}),
        ("range090", {"EVENT_RANGE_ATR_MIN": 0.90}),
        ("fraction040", {"EVENT_BODY_FRACTION_MIN": 0.40}),
        ("fraction060", {"EVENT_BODY_FRACTION_MIN": 0.60}),
        ("fraction070", {"EVENT_BODY_FRACTION_MIN": 0.70}),
        ("close060", {"EVENT_CLOSE_FRACTION": 0.60}),
        ("close080", {"EVENT_CLOSE_FRACTION": 0.80}),
        ("close090", {"EVENT_CLOSE_FRACTION": 0.90}),
    ),
    "windows": (
        ("base", {}),
        ("baseline040", {"BASELINE_BARS": 40}),
        ("baseline080", {"BASELINE_BARS": 80}),
        ("baseline100", {"BASELINE_BARS": 100}),
        ("recent016", {"RECENT_BARS": 16}),
        ("recent024", {"RECENT_BARS": 24}),
        ("recent028", {"RECENT_BARS": 28}),
    ),
}


def _view(summary):
    return {
        key: summary[key]
        for key in (
            "closed",
            "wins",
            "win_rate",
            "net_profit",
            "profit_factor",
            "max_drawdown",
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
            380,
            months,
            "M5",
            0.20,
            0.01,
            end,
            300,
            cfg,
            prepared,
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
