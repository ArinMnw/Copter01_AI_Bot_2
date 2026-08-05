# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S385."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
}

GROUPS = {
    "cusum": (
        ("base", {}),
        ("q055", {"TAIL_QUANTILE": 0.55}),
        ("q065", {"TAIL_QUANTILE": 0.65}),
        ("cusum050", {"CUSUM_MIN": 0.50}),
        ("cusum075", {"CUSUM_MIN": 0.75}),
        ("cusum125", {"CUSUM_MIN": 1.25}),
        ("cusum150", {"CUSUM_MIN": 1.50}),
        ("drift000", {"CUSUM_DRIFT": 0.00}),
        ("drift060", {"CUSUM_DRIFT": 0.06}),
        ("rise000", {"TAIL_RATE_RISE_MIN": 0.00}),
        ("rise050", {"TAIL_RATE_RISE_MIN": 0.05}),
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
        ("body050", {"EVENT_BODY_ATR_MIN": 0.50}),
        ("body075", {"EVENT_BODY_ATR_MIN": 0.75}),
        ("fraction065", {"EVENT_BODY_FRACTION_MIN": 0.65}),
        ("fraction075", {"EVENT_BODY_FRACTION_MIN": 0.75}),
        ("close065", {"EVENT_CLOSE_FRACTION": 0.65}),
        ("close085", {"EVENT_CLOSE_FRACTION": 0.85}),
    ),
    "focused": (
        ("base", {}),
        ("rise050", {"TAIL_RATE_RISE_MIN": 0.05}),
        ("drift060", {"CUSUM_DRIFT": 0.06}),
        ("rise050_drift060", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06}),
        ("rise050_body060", {"TAIL_RATE_RISE_MIN": 0.05, "EVENT_BODY_ATR_MIN": 0.60}),
        ("rise050_fraction070", {"TAIL_RATE_RISE_MIN": 0.05, "EVENT_BODY_FRACTION_MIN": 0.70}),
        ("rise050_volume105", {"TAIL_RATE_RISE_MIN": 0.05, "EVENT_VOLUME_RATIO_MIN": 1.05}),
    ),
    "windows_risk": (
        ("core", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06}),
        ("baseline060", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "BASELINE_BARS": 60}),
        ("baseline100", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "BASELINE_BARS": 100}),
        ("recent020", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "RECENT_BARS": 20}),
        ("recent024", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "RECENT_BARS": 24}),
        ("recent032", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "RECENT_BARS": 32}),
        ("buffer014", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "SL_BUFFER_ATR": 0.14}),
        ("buffer016", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "SL_BUFFER_ATR": 0.16}),
        ("buffer018", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "SL_BUFFER_ATR": 0.18}),
        ("buffer020", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "SL_BUFFER_ATR": 0.20}),
        ("buffer022", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "SL_BUFFER_ATR": 0.22}),
        ("maxrisk150", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "MAX_RISK_ATR": 1.50}),
        ("maxrisk200", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "MAX_RISK_ATR": 2.00}),
    ),
    "interaction": (
        ("core", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06}),
        ("b100", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "BASELINE_BARS": 100}),
        ("r20", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "RECENT_BARS": 20}),
        ("b100_r20", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "BASELINE_BARS": 100, "RECENT_BARS": 20}),
        ("b100_r20_q065", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "BASELINE_BARS": 100, "RECENT_BARS": 20, "TAIL_QUANTILE": 0.65}),
        ("b100_r20_path025", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "BASELINE_BARS": 100, "RECENT_BARS": 20, "PATH_EFFICIENCY_MIN": 0.25}),
        ("b100_r20_direction020", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "BASELINE_BARS": 100, "RECENT_BARS": 20, "TAIL_DIRECTIONAL_VOLUME_MIN": 0.20}),
    ),
    "local": (
        ("core", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "RECENT_BARS": 20}),
        ("recent018", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "RECENT_BARS": 18}),
        ("recent019", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "RECENT_BARS": 19}),
        ("recent021", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "RECENT_BARS": 21}),
        ("recent022", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "RECENT_BARS": 22}),
        ("rise040", {"TAIL_RATE_RISE_MIN": 0.04, "CUSUM_DRIFT": 0.06, "RECENT_BARS": 20}),
        ("rise060", {"TAIL_RATE_RISE_MIN": 0.06, "CUSUM_DRIFT": 0.06, "RECENT_BARS": 20}),
        ("drift040", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.04, "RECENT_BARS": 20}),
        ("drift080", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.08, "RECENT_BARS": 20}),
        ("body060", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "RECENT_BARS": 20, "EVENT_BODY_ATR_MIN": 0.60}),
        ("fraction070", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "RECENT_BARS": 20, "EVENT_BODY_FRACTION_MIN": 0.70}),
        ("fraction074", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "RECENT_BARS": 20, "EVENT_BODY_FRACTION_MIN": 0.74}),
        ("buffer018", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "RECENT_BARS": 20, "SL_BUFFER_ATR": 0.18}),
        ("buffer020", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "RECENT_BARS": 20, "SL_BUFFER_ATR": 0.20}),
    ),
    "final": (
        ("core", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.06, "RECENT_BARS": 20}),
        ("rise060", {"TAIL_RATE_RISE_MIN": 0.06, "CUSUM_DRIFT": 0.06, "RECENT_BARS": 20}),
        ("drift080", {"TAIL_RATE_RISE_MIN": 0.05, "CUSUM_DRIFT": 0.08, "RECENT_BARS": 20}),
        ("rise060_drift080", {"TAIL_RATE_RISE_MIN": 0.06, "CUSUM_DRIFT": 0.08, "RECENT_BARS": 20}),
        ("rise070_drift080", {"TAIL_RATE_RISE_MIN": 0.07, "CUSUM_DRIFT": 0.08, "RECENT_BARS": 20}),
        ("rise060_drift100", {"TAIL_RATE_RISE_MIN": 0.06, "CUSUM_DRIFT": 0.10, "RECENT_BARS": 20}),
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
            385, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
