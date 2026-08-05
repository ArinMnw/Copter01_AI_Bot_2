# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S402."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
    "latest": (2, "2026-07-30T00:00:00+07:00"),
}

GROUPS = {
    "jump": (
        ("base", {}),
        ("share000", {"JUMP_SHARE_MIN": 0.00}),
        ("share020", {"JUMP_SHARE_MIN": 0.20}),
        ("ratio100", {"JUMP_SHARE_RATIO_MIN": 1.00}),
        ("ratio140", {"JUMP_SHARE_RATIO_MIN": 1.40}),
        ("ratio180", {"JUMP_SHARE_RATIO_MIN": 1.80}),
        ("rise000", {"JUMP_SHARE_RISE_MIN": 0.00}),
        ("rise060", {"JUMP_SHARE_RISE_MIN": 0.06}),
        ("energy000", {"JUMP_ENERGY_ATR2_MIN": 0.00}),
        ("energy035", {"JUMP_ENERGY_ATR2_MIN": 0.35}),
        ("recent020", {"BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("recent028", {"BASELINE_BARS": 84, "RECENT_BARS": 28}),
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
    "direction": (
        ("continuation", {}),
        ("fade", {"FADE_JUMP": True}),
        ("fade_loose", {"FADE_JUMP": True, "JUMP_SHARE_MIN": 0.00}),
        ("fade_share020", {"FADE_JUMP": True, "JUMP_SHARE_MIN": 0.20}),
        ("fade_ratio180", {"FADE_JUMP": True, "JUMP_SHARE_RATIO_MIN": 1.80}),
        ("fade_recent020", {"FADE_JUMP": True, "BASELINE_BARS": 60,
                            "RECENT_BARS": 20}),
        ("fade_recent028", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                            "RECENT_BARS": 28}),
    ),
    "fade28": (
        ("base", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                  "RECENT_BARS": 28}),
        ("share000", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                      "RECENT_BARS": 28, "JUMP_SHARE_MIN": 0.00}),
        ("share008", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                      "RECENT_BARS": 28, "JUMP_SHARE_MIN": 0.08}),
        ("share016", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                      "RECENT_BARS": 28, "JUMP_SHARE_MIN": 0.16}),
        ("share020", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                      "RECENT_BARS": 28, "JUMP_SHARE_MIN": 0.20}),
        ("share024", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                      "RECENT_BARS": 28, "JUMP_SHARE_MIN": 0.24}),
        ("ratio100", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                      "RECENT_BARS": 28, "JUMP_SHARE_RATIO_MIN": 1.00}),
        ("ratio140", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                      "RECENT_BARS": 28, "JUMP_SHARE_RATIO_MIN": 1.40}),
        ("ratio180", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                      "RECENT_BARS": 28, "JUMP_SHARE_RATIO_MIN": 1.80}),
        ("rise000", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                     "RECENT_BARS": 28, "JUMP_SHARE_RISE_MIN": 0.00}),
        ("rise060", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                     "RECENT_BARS": 28, "JUMP_SHARE_RISE_MIN": 0.06}),
        ("energy000", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                       "RECENT_BARS": 28, "JUMP_ENERGY_ATR2_MIN": 0.00}),
        ("energy035", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                       "RECENT_BARS": 28, "JUMP_ENERGY_ATR2_MIN": 0.35}),
    ),
    "focused": (
        ("base", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                  "RECENT_BARS": 28}),
        ("q160", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                  "RECENT_BARS": 28, "JUMP_SHARE_RATIO_MIN": 1.60}),
        ("q180", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                  "RECENT_BARS": 28, "JUMP_SHARE_RATIO_MIN": 1.80}),
        ("q200", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                  "RECENT_BARS": 28, "JUMP_SHARE_RATIO_MIN": 2.00}),
        ("rise060", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                     "RECENT_BARS": 28, "JUMP_SHARE_RISE_MIN": 0.06}),
        ("rise090", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                     "RECENT_BARS": 28, "JUMP_SHARE_RISE_MIN": 0.09}),
        ("q180_r060", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                       "RECENT_BARS": 28, "JUMP_SHARE_RATIO_MIN": 1.80,
                       "JUMP_SHARE_RISE_MIN": 0.06}),
        ("q180_share020", {"FADE_JUMP": True, "BASELINE_BARS": 84,
                           "RECENT_BARS": 28, "JUMP_SHARE_RATIO_MIN": 1.80,
                           "JUMP_SHARE_MIN": 0.20}),
    ),
    "buffer_local": (
        ("b010", {"SL_BUFFER_ATR": 0.10}),
        ("b012", {"SL_BUFFER_ATR": 0.12}),
        ("b014", {"SL_BUFFER_ATR": 0.14}),
        ("b016", {"SL_BUFFER_ATR": 0.16}),
        ("b018", {"SL_BUFFER_ATR": 0.18}),
        ("b020", {"SL_BUFFER_ATR": 0.20}),
        ("b022", {"SL_BUFFER_ATR": 0.22}),
        ("b024", {"SL_BUFFER_ATR": 0.24}),
    ),
    "combo": (
        ("b014_rr7", {"SL_BUFFER_ATR": 0.14}),
        ("b014_rr8", {"SL_BUFFER_ATR": 0.14, "TP_RR": 8.0}),
        ("b020_rr7", {"SL_BUFFER_ATR": 0.20}),
        ("b020_rr8", {"SL_BUFFER_ATR": 0.20, "TP_RR": 8.0}),
        ("b020_rr9", {"SL_BUFFER_ATR": 0.20, "TP_RR": 9.0}),
        ("b020_rr11", {"SL_BUFFER_ATR": 0.20, "TP_RR": 11.0}),
    ),
    "rr_tail": (
        ("rr7", {"SL_BUFFER_ATR": 0.20, "TP_RR": 7.0}),
        ("rr8", {"SL_BUFFER_ATR": 0.20, "TP_RR": 8.0}),
        ("rr9", {"SL_BUFFER_ATR": 0.20, "TP_RR": 9.0}),
        ("rr10", {"SL_BUFFER_ATR": 0.20, "TP_RR": 10.0}),
        ("rr11", {"SL_BUFFER_ATR": 0.20, "TP_RR": 11.0}),
        ("rr12", {"SL_BUFFER_ATR": 0.20, "TP_RR": 12.0}),
        ("rr13", {"SL_BUFFER_ATR": 0.20, "TP_RR": 13.0}),
        ("rr14", {"SL_BUFFER_ATR": 0.20, "TP_RR": 14.0}),
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
            402, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
