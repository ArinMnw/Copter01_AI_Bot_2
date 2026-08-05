# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S384."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
}

GROUPS = {
    "clock": (
        ("base", {}),
        ("q055", {"TAIL_QUANTILE": 0.55}),
        ("q065", {"TAIL_QUANTILE": 0.65}),
        ("compression100", {"INTERARRIVAL_COMPRESSION_MIN": 1.00}),
        ("compression130", {"INTERARRIVAL_COMPRESSION_MIN": 1.30}),
        ("compression150", {"INTERARRIVAL_COMPRESSION_MIN": 1.50}),
        ("rise000", {"TAIL_RATE_RISE_MIN": 0.00}),
        ("rise040", {"TAIL_RATE_RISE_MIN": 0.04}),
        ("rise060", {"TAIL_RATE_RISE_MIN": 0.06}),
        ("events4", {"MIN_TAIL_EVENTS": 4}),
        ("direction010", {"TAIL_DIRECTIONAL_VOLUME_MIN": 0.10}),
        ("direction025", {"TAIL_DIRECTIONAL_VOLUME_MIN": 0.25}),
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
    "event": (
        ("base", {}),
        ("volume100", {"EVENT_VOLUME_RATIO_MIN": 1.00}),
        ("volume120", {"EVENT_VOLUME_RATIO_MIN": 1.20}),
        ("body035", {"EVENT_BODY_ATR_MIN": 0.35}),
        ("body065", {"EVENT_BODY_ATR_MIN": 0.65}),
        ("fraction060", {"EVENT_BODY_FRACTION_MIN": 0.60}),
        ("fraction075", {"EVENT_BODY_FRACTION_MIN": 0.75}),
        ("close065", {"EVENT_CLOSE_FRACTION": 0.65}),
        ("close085", {"EVENT_CLOSE_FRACTION": 0.85}),
    ),
    "focused": (
        ("base", {}),
        ("q055", {"TAIL_QUANTILE": 0.55}),
        ("rise000", {"TAIL_RATE_RISE_MIN": 0.00}),
        ("q055_rise000", {"TAIL_QUANTILE": 0.55, "TAIL_RATE_RISE_MIN": 0.00}),
        ("body065", {"EVENT_BODY_ATR_MIN": 0.65}),
        ("q055_rise000_body065", {"TAIL_QUANTILE": 0.55, "TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65}),
        ("q055_rise000_fraction060", {"TAIL_QUANTILE": 0.55, "TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_FRACTION_MIN": 0.60}),
    ),
    "windows_risk": (
        ("rise000", {"TAIL_RATE_RISE_MIN": 0.00}),
        ("core", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65}),
        ("baseline060", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "BASELINE_BARS": 60}),
        ("baseline100", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "BASELINE_BARS": 100}),
        ("recent020", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "RECENT_BARS": 20}),
        ("recent024", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "RECENT_BARS": 24}),
        ("recent032", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "RECENT_BARS": 32}),
        ("buffer014", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "SL_BUFFER_ATR": 0.14}),
        ("buffer016", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "SL_BUFFER_ATR": 0.16}),
        ("buffer018", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "SL_BUFFER_ATR": 0.18}),
        ("buffer020", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "SL_BUFFER_ATR": 0.20}),
        ("buffer022", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "SL_BUFFER_ATR": 0.22}),
    ),
    "local": (
        ("core", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65}),
        ("compression105", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "INTERARRIVAL_COMPRESSION_MIN": 1.05}),
        ("compression110", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "INTERARRIVAL_COMPRESSION_MIN": 1.10}),
        ("compression120", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "INTERARRIVAL_COMPRESSION_MIN": 1.20}),
        ("compression125", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "INTERARRIVAL_COMPRESSION_MIN": 1.25}),
        ("body060", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.60}),
        ("body070", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.70}),
        ("volume105", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "EVENT_VOLUME_RATIO_MIN": 1.05}),
        ("volume115", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "EVENT_VOLUME_RATIO_MIN": 1.15}),
        ("fraction068", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "EVENT_BODY_FRACTION_MIN": 0.68}),
        ("fraction072", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "EVENT_BODY_FRACTION_MIN": 0.72}),
        ("direction018", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "TAIL_DIRECTIONAL_VOLUME_MIN": 0.18}),
    ),
    "final": (
        ("core", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65}),
        ("fraction071", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "EVENT_BODY_FRACTION_MIN": 0.71}),
        ("fraction072", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "EVENT_BODY_FRACTION_MIN": 0.72}),
        ("fraction073", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "EVENT_BODY_FRACTION_MIN": 0.73}),
        ("compression113", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "INTERARRIVAL_COMPRESSION_MIN": 1.13}),
        ("compression117", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "INTERARRIVAL_COMPRESSION_MIN": 1.17}),
        ("body064", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.64}),
        ("body066", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.66}),
        ("f072_c113", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "EVENT_BODY_FRACTION_MIN": 0.72, "INTERARRIVAL_COMPRESSION_MIN": 1.13}),
        ("f072_c117", {"TAIL_RATE_RISE_MIN": 0.00, "EVENT_BODY_ATR_MIN": 0.65, "EVENT_BODY_FRACTION_MIN": 0.72, "INTERARRIVAL_COMPRESSION_MIN": 1.17}),
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
            384, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
