# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S378."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
}

GROUPS = {
    "ultimate": (
        (
            "final",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.80,
                "SL_BUFFER_ATR": 0.18,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "rr8",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.80,
                "SL_BUFFER_ATR": 0.18,
                "TP_RR": 8.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "rr10",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.80,
                "SL_BUFFER_ATR": 0.18,
                "TP_RR": 10.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "be001",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.80,
                "SL_BUFFER_ATR": 0.18,
                "TP_RR": 9.0,
                "BE_RR": 0.01,
            },
        ),
        (
            "close078",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.78,
                "SL_BUFFER_ATR": 0.18,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "close082",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.82,
                "SL_BUFFER_ATR": 0.18,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
            },
        ),
    ),
    "buffer_local": tuple(
        (
            f"buffer{int(buffer * 100):03d}",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.80,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
                "SL_BUFFER_ATR": buffer,
            },
        )
        for buffer in (0.12, 0.14, 0.16, 0.18, 0.20, 0.24)
    ),
    "risk": (
        (
            "all",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.80,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "buffer004",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.80,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
                "SL_BUFFER_ATR": 0.04,
            },
        ),
        (
            "buffer012",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.80,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
                "SL_BUFFER_ATR": 0.12,
            },
        ),
        (
            "buffer016",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.80,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
                "SL_BUFFER_ATR": 0.16,
            },
        ),
        (
            "maxrisk125",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.80,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
                "MAX_RISK_ATR": 1.25,
            },
        ),
        (
            "maxrisk150",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.80,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
                "MAX_RISK_ATR": 1.50,
            },
        ),
        (
            "maxrisk200",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.80,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
                "MAX_RISK_ATR": 2.00,
            },
        ),
        (
            "minrisk100",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.80,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
                "MIN_RISK_ABS": 1.00,
            },
        ),
        (
            "minrisk150",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.80,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
                "MIN_RISK_ABS": 1.50,
            },
        ),
    ),
    "interaction": (
        ("base", {}),
        (
            "state_event",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.80,
            },
        ),
        (
            "payoff",
            {
                "TP_RR": 9.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "all",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.80,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "all_rr8",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.80,
                "TP_RR": 8.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "all_rr10",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.80,
                "TP_RR": 10.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "all_close075",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.75,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "all_close085",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.12,
                "EVENT_CLOSE_FRACTION": 0.85,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "all_exp010",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.10,
                "EVENT_CLOSE_FRACTION": 0.80,
                "TP_RR": 9.0,
                "BE_RR": 0.02,
            },
        ),
        (
            "all_exp014",
            {
                "PERSISTENCE_EXPANSION_MIN": 0.14,
                "EVENT_CLOSE_FRACTION": 0.80,
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
    "state": (
        ("base", {}),
        ("high105", {"HIGH_RANGE_RATIO": 1.05}),
        ("high125", {"HIGH_RANGE_RATIO": 1.25}),
        ("high135", {"HIGH_RANGE_RATIO": 1.35}),
        ("persist055", {"PERSISTENCE_MIN": 0.55}),
        ("persist065", {"PERSISTENCE_MIN": 0.65}),
        ("persist070", {"PERSISTENCE_MIN": 0.70}),
        ("expansion004", {"PERSISTENCE_EXPANSION_MIN": 0.04}),
        ("expansion012", {"PERSISTENCE_EXPANSION_MIN": 0.12}),
        ("expansion016", {"PERSISTENCE_EXPANSION_MIN": 0.16}),
        ("support04", {"RECENT_SUPPORT_MIN": 4}),
        ("support06", {"RECENT_SUPPORT_MIN": 6}),
        ("support08", {"RECENT_SUPPORT_MIN": 8}),
    ),
    "event": (
        ("base", {}),
        ("range105", {"EVENT_RANGE_RATIO_MIN": 1.05}),
        ("range135", {"EVENT_RANGE_RATIO_MIN": 1.35}),
        ("range150", {"EVENT_RANGE_RATIO_MIN": 1.50}),
        ("body035", {"EVENT_BODY_ATR_MIN": 0.35}),
        ("body065", {"EVENT_BODY_ATR_MIN": 0.65}),
        ("body080", {"EVENT_BODY_ATR_MIN": 0.80}),
        ("fraction045", {"EVENT_BODY_FRACTION_MIN": 0.45}),
        ("fraction065", {"EVENT_BODY_FRACTION_MIN": 0.65}),
        ("fraction075", {"EVENT_BODY_FRACTION_MIN": 0.75}),
        ("close060", {"EVENT_CLOSE_FRACTION": 0.60}),
        ("close080", {"EVENT_CLOSE_FRACTION": 0.80}),
        ("close090", {"EVENT_CLOSE_FRACTION": 0.90}),
    ),
    "windows": (
        ("base", {}),
        ("baseline048", {"BASELINE_BARS": 48}),
        ("baseline060", {"BASELINE_BARS": 60}),
        ("baseline090", {"BASELINE_BARS": 90}),
        ("baseline120", {"BASELINE_BARS": 120}),
        ("recent020", {"RECENT_BARS": 20}),
        ("recent024", {"RECENT_BARS": 24}),
        ("recent036", {"RECENT_BARS": 36}),
        ("recent048", {"RECENT_BARS": 48}),
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
            378,
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
