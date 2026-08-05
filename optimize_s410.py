# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S410."""

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
        ("contract", {"CONTRACT_SHAPE": True}),
        ("fade", {"FADE_PATH": True}),
        ("ratio100", {"SHAPE_RATIO_MIN": 1.00}),
        ("ratio108", {"SHAPE_RATIO_MIN": 1.08}),
        ("rise000", {"SHAPE_RISE_MIN": 0.00}),
        ("rise006", {"SHAPE_RISE_MIN": 0.06}),
        ("sn090", {"SN_SCALE_RATIO_MIN": 0.90}),
        ("sn110", {"SN_SCALE_RATIO_MIN": 1.10}),
        ("snrise002", {"SN_RISE_ATR_MIN": 0.02}),
        ("path006", {"PATH_EFFICIENCY_MIN": 0.06}),
        ("path020", {"PATH_EFFICIENCY_MIN": 0.20}),
        ("recent020", {"BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("recent028", {"BASELINE_BARS": 84, "RECENT_BARS": 28}),
        ("session0715", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15}),
        ("session1318", {"SESSION_START_HOUR": 13, "SESSION_END_HOUR": 18}),
    ),
    "finalists": (
        ("base", {}),
        ("ratio108", {"SHAPE_RATIO_MIN": 1.08}),
        ("rise006", {"SHAPE_RISE_MIN": 0.06}),
        ("sn110", {"SN_SCALE_RATIO_MIN": 1.10}),
        ("path006", {"PATH_EFFICIENCY_MIN": 0.06}),
        ("path020", {"PATH_EFFICIENCY_MIN": 0.20}),
        ("recent020", {"BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("recent028", {"BASELINE_BARS": 84, "RECENT_BARS": 28}),
        ("session0715", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15}),
    ),
    "direction_session": (
        ("base", {}),
        ("buy_only", {"ALLOW_SELL": False}),
        ("sell_only", {"ALLOW_BUY": False}),
        ("session1519", {"SESSION_START_HOUR": 15,
                         "SESSION_END_HOUR": 19}),
        ("session1723", {"SESSION_START_HOUR": 17,
                         "SESSION_END_HOUR": 23}),
        ("session1923", {"SESSION_START_HOUR": 19,
                         "SESSION_END_HOUR": 23}),
        ("recent028_buy", {"BASELINE_BARS": 84, "RECENT_BARS": 28,
                           "ALLOW_SELL": False}),
        ("recent028_sell", {"BASELINE_BARS": 84, "RECENT_BARS": 28,
                            "ALLOW_BUY": False}),
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
        summary, _ = backtest(410, months, "M5", 0.20, 0.01, end, 300,
                              cfg, prepared)
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
