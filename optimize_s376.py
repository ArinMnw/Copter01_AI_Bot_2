# -*- coding: utf-8 -*-
"""Cross-window falsification probes for S376 persistence mode."""

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
            "recent024_rr9",
            {
                "LEAD_CORRELATION_RATIO_MIN": 1.40,
                "RECENT_BARS": 24,
                "TP_RR": 9.0,
            },
        ),
        (
            "recent024_rr9_be001",
            {
                "LEAD_CORRELATION_RATIO_MIN": 1.40,
                "RECENT_BARS": 24,
                "TP_RR": 9.0,
                "BE_RR": 0.01,
            },
        ),
    ),
    "final": (
        (
            "recent024",
            {
                "LEAD_CORRELATION_RATIO_MIN": 1.40,
                "RECENT_BARS": 24,
            },
        ),
        (
            "recent024_be001",
            {
                "LEAD_CORRELATION_RATIO_MIN": 1.40,
                "RECENT_BARS": 24,
                "BE_RR": 0.01,
            },
        ),
        (
            "recent024_rr8",
            {
                "LEAD_CORRELATION_RATIO_MIN": 1.40,
                "RECENT_BARS": 24,
                "TP_RR": 8.0,
            },
        ),
        (
            "recent024_rr9",
            {
                "LEAD_CORRELATION_RATIO_MIN": 1.40,
                "RECENT_BARS": 24,
                "TP_RR": 9.0,
            },
        ),
        (
            "recent024_corr025",
            {
                "LEAD_CORRELATION_RATIO_MIN": 1.40,
                "RECENT_BARS": 24,
                "LEAD_CORRELATION_MIN": 0.25,
            },
        ),
        (
            "recent024_corr030",
            {
                "LEAD_CORRELATION_RATIO_MIN": 1.40,
                "RECENT_BARS": 24,
                "LEAD_CORRELATION_MIN": 0.30,
            },
        ),
    ),
    "refine": (
        ("ratio140", {"LEAD_CORRELATION_RATIO_MIN": 1.40}),
        (
            "buy_only",
            {
                "LEAD_CORRELATION_RATIO_MIN": 1.40,
                "ALLOW_SELL": False,
            },
        ),
        (
            "sell_only",
            {
                "LEAD_CORRELATION_RATIO_MIN": 1.40,
                "ALLOW_BUY": False,
            },
        ),
        ("rr8", {"LEAD_CORRELATION_RATIO_MIN": 1.40, "TP_RR": 8.0}),
        ("rr9", {"LEAD_CORRELATION_RATIO_MIN": 1.40, "TP_RR": 9.0}),
        ("be001", {"LEAD_CORRELATION_RATIO_MIN": 1.40, "BE_RR": 0.01}),
        ("be002", {"LEAD_CORRELATION_RATIO_MIN": 1.40, "BE_RR": 0.02}),
        ("be008", {"LEAD_CORRELATION_RATIO_MIN": 1.40, "BE_RR": 0.08}),
        ("be012", {"LEAD_CORRELATION_RATIO_MIN": 1.40, "BE_RR": 0.12}),
        (
            "baseline080",
            {
                "LEAD_CORRELATION_RATIO_MIN": 1.40,
                "BASELINE_BARS": 80,
            },
        ),
        (
            "recent024",
            {
                "LEAD_CORRELATION_RATIO_MIN": 1.40,
                "RECENT_BARS": 24,
            },
        ),
    ),
    "focus": (
        ("base", {}),
        ("corr025", {"LEAD_CORRELATION_MIN": 0.25}),
        ("corr030", {"LEAD_CORRELATION_MIN": 0.30}),
        ("volume090", {"EVENT_VOLUME_RATIO_MIN": 0.90}),
        ("ratio140", {"LEAD_CORRELATION_RATIO_MIN": 1.40}),
        (
            "corr030_volume090",
            {
                "LEAD_CORRELATION_MIN": 0.30,
                "EVENT_VOLUME_RATIO_MIN": 0.90,
            },
        ),
        (
            "corr030_ratio140",
            {
                "LEAD_CORRELATION_MIN": 0.30,
                "LEAD_CORRELATION_RATIO_MIN": 1.40,
            },
        ),
        (
            "corr030_body050",
            {
                "LEAD_CORRELATION_MIN": 0.30,
                "EVENT_BODY_ATR_MIN": 0.50,
            },
        ),
    ),
    "payoff": (
        ("base", {}),
        ("buy_only", {"ALLOW_SELL": False}),
        ("sell_only", {"ALLOW_BUY": False}),
        ("rr8", {"TP_RR": 8.0}),
        ("rr9", {"TP_RR": 9.0}),
        ("be001", {"BE_RR": 0.01}),
        ("be002", {"BE_RR": 0.02}),
        ("be008", {"BE_RR": 0.08}),
        ("be012", {"BE_RR": 0.12}),
    ),
    "shape": (
        ("base", {}),
        ("corr015", {"LEAD_CORRELATION_MIN": 0.15}),
        ("corr025", {"LEAD_CORRELATION_MIN": 0.25}),
        ("corr030", {"LEAD_CORRELATION_MIN": 0.30}),
        ("ratio105", {"LEAD_CORRELATION_RATIO_MIN": 1.05}),
        ("ratio140", {"LEAD_CORRELATION_RATIO_MIN": 1.40}),
        ("ratio160", {"LEAD_CORRELATION_RATIO_MIN": 1.60}),
        ("volume090", {"EVENT_VOLUME_RATIO_MIN": 0.90}),
        ("volume120", {"EVENT_VOLUME_RATIO_MIN": 1.20}),
        ("volume140", {"EVENT_VOLUME_RATIO_MIN": 1.40}),
        ("body015", {"EVENT_BODY_ATR_MIN": 0.15}),
        ("body035", {"EVENT_BODY_ATR_MIN": 0.35}),
        ("body050", {"EVENT_BODY_ATR_MIN": 0.50}),
        ("range045", {"EVENT_RANGE_ATR_MIN": 0.45}),
        ("range080", {"EVENT_RANGE_ATR_MIN": 0.80}),
        ("fraction035", {"EVENT_BODY_FRACTION_MIN": 0.35}),
        ("fraction055", {"EVENT_BODY_FRACTION_MIN": 0.55}),
        ("fraction065", {"EVENT_BODY_FRACTION_MIN": 0.65}),
    ),
    "windows": (
        ("base", {}),
        ("baseline040", {"BASELINE_BARS": 40}),
        ("baseline080", {"BASELINE_BARS": 80}),
        ("baseline100", {"BASELINE_BARS": 100}),
        ("recent016", {"RECENT_BARS": 16}),
        ("recent024", {"RECENT_BARS": 24}),
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
            376,
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
