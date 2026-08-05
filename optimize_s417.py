# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S417."""

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
        ("fade", {"FADE_PATH": True}),
        ("contract", {"CONTRACT_VR": True}),
        ("contract_fade", {"CONTRACT_VR": True, "FADE_PATH": True}),
        ("horizon2", {"VR_HORIZON": 2}),
        ("horizon6", {"VR_HORIZON": 6}),
        ("expand100", {"VR_EXPANSION_RATIO_MIN": 1.00,
                       "VR_RISE_MIN": 0.00}),
        ("expand130", {"VR_EXPANSION_RATIO_MIN": 1.30,
                       "VR_RISE_MIN": 0.15}),
        ("path004", {"PATH_EFFICIENCY_MIN": 0.04}),
        ("path018", {"PATH_EFFICIENCY_MIN": 0.18}),
        ("recent020", {"BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("recent028", {"BASELINE_BARS": 84, "RECENT_BARS": 28}),
        ("session0007", {"SESSION_START_HOUR": 0, "SESSION_END_HOUR": 7}),
        ("session0715", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15}),
        ("session1523", {"SESSION_START_HOUR": 15, "SESSION_END_HOUR": 23}),
        ("buy_only", {"ALLOW_SELL": False}),
        ("sell_only", {"ALLOW_BUY": False}),
    ),
    "finalists": (
        ("base", {}),
        ("contract", {"CONTRACT_VR": True}),
        ("contract_fade", {"CONTRACT_VR": True, "FADE_PATH": True}),
        ("horizon2", {"VR_HORIZON": 2}),
        ("horizon6", {"VR_HORIZON": 6}),
        ("recent020", {"BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("session0715", {"SESSION_START_HOUR": 7, "SESSION_END_HOUR": 15}),
        ("sell_only", {"ALLOW_BUY": False}),
        ("session0715_sell", {"SESSION_START_HOUR": 7,
                              "SESSION_END_HOUR": 15,
                              "ALLOW_BUY": False}),
        ("horizon6_sell", {"VR_HORIZON": 6, "ALLOW_BUY": False}),
        ("recent020_sell", {"BASELINE_BARS": 60, "RECENT_BARS": 20,
                            "ALLOW_BUY": False}),
    ),
    "contract_fade_opt": (
        ("cf_base", {"CONTRACT_VR": True, "FADE_PATH": True}),
        ("cf_h2", {"CONTRACT_VR": True, "FADE_PATH": True,
                   "VR_HORIZON": 2}),
        ("cf_h6", {"CONTRACT_VR": True, "FADE_PATH": True,
                   "VR_HORIZON": 6}),
        ("cf_ratio075", {"CONTRACT_VR": True, "FADE_PATH": True,
                         "VR_CONTRACTION_RATIO_MAX": 0.75}),
        ("cf_ratio095", {"CONTRACT_VR": True, "FADE_PATH": True,
                         "VR_CONTRACTION_RATIO_MAX": 0.95}),
        ("cf_drop000", {"CONTRACT_VR": True, "FADE_PATH": True,
                        "VR_DROP_MIN": 0.00}),
        ("cf_drop004", {"CONTRACT_VR": True, "FADE_PATH": True,
                        "VR_DROP_MIN": 0.04}),
        ("cf_drop012", {"CONTRACT_VR": True, "FADE_PATH": True,
                        "VR_DROP_MIN": 0.12}),
        ("cf_abs090", {"CONTRACT_VR": True, "FADE_PATH": True,
                       "VR_ABS_MAX": 0.90}),
        ("cf_abs150", {"CONTRACT_VR": True, "FADE_PATH": True,
                       "VR_ABS_MAX": 1.50}),
        ("cf_path004", {"CONTRACT_VR": True, "FADE_PATH": True,
                        "PATH_EFFICIENCY_MIN": 0.04}),
        ("cf_path018", {"CONTRACT_VR": True, "FADE_PATH": True,
                        "PATH_EFFICIENCY_MIN": 0.18}),
        ("cf_recent020", {"CONTRACT_VR": True, "FADE_PATH": True,
                          "BASELINE_BARS": 60, "RECENT_BARS": 20}),
        ("cf_recent028", {"CONTRACT_VR": True, "FADE_PATH": True,
                          "BASELINE_BARS": 84, "RECENT_BARS": 28}),
        ("cf_buy", {"CONTRACT_VR": True, "FADE_PATH": True,
                    "ALLOW_SELL": False}),
        ("cf_sell", {"CONTRACT_VR": True, "FADE_PATH": True,
                     "ALLOW_BUY": False}),
        ("cf_tp750", {"CONTRACT_VR": True, "FADE_PATH": True,
                      "TP_RR": 7.50}),
        ("cf_tp800", {"CONTRACT_VR": True, "FADE_PATH": True,
                      "TP_RR": 8.00}),
        ("cf_body055", {"CONTRACT_VR": True, "FADE_PATH": True,
                        "EVENT_BODY_ATR_MIN": 0.55}),
        ("cf_volume120", {"CONTRACT_VR": True, "FADE_PATH": True,
                          "EVENT_VOLUME_RATIO_MIN": 1.20}),
    ),
    "cf_finalists": (
        ("cf_base", {"CONTRACT_VR": True, "FADE_PATH": True}),
        ("cf_h6", {"CONTRACT_VR": True, "FADE_PATH": True,
                   "VR_HORIZON": 6}),
        ("cf_ratio075", {"CONTRACT_VR": True, "FADE_PATH": True,
                         "VR_CONTRACTION_RATIO_MAX": 0.75}),
        ("cf_path018", {"CONTRACT_VR": True, "FADE_PATH": True,
                        "PATH_EFFICIENCY_MIN": 0.18}),
        ("cf_sell", {"CONTRACT_VR": True, "FADE_PATH": True,
                     "ALLOW_BUY": False}),
        ("cf_body055", {"CONTRACT_VR": True, "FADE_PATH": True,
                        "EVENT_BODY_ATR_MIN": 0.55}),
        ("cf_volume120", {"CONTRACT_VR": True, "FADE_PATH": True,
                          "EVENT_VOLUME_RATIO_MIN": 1.20}),
    ),
    "cf_cliff": (
        ("h3", {"CONTRACT_VR": True, "FADE_PATH": True,
                "VR_HORIZON": 3}),
        ("h4", {"CONTRACT_VR": True, "FADE_PATH": True,
                "VR_HORIZON": 4}),
        ("h5", {"CONTRACT_VR": True, "FADE_PATH": True,
                "VR_HORIZON": 5}),
        ("ratio080", {"CONTRACT_VR": True, "FADE_PATH": True,
                      "VR_CONTRACTION_RATIO_MAX": 0.80}),
        ("ratio085", {"CONTRACT_VR": True, "FADE_PATH": True,
                      "VR_CONTRACTION_RATIO_MAX": 0.85}),
        ("ratio090", {"CONTRACT_VR": True, "FADE_PATH": True,
                      "VR_CONTRACTION_RATIO_MAX": 0.90}),
        ("path008", {"CONTRACT_VR": True, "FADE_PATH": True,
                     "PATH_EFFICIENCY_MIN": 0.08}),
        ("path010", {"CONTRACT_VR": True, "FADE_PATH": True,
                     "PATH_EFFICIENCY_MIN": 0.10}),
        ("path012", {"CONTRACT_VR": True, "FADE_PATH": True,
                     "PATH_EFFICIENCY_MIN": 0.12}),
        ("body040", {"CONTRACT_VR": True, "FADE_PATH": True,
                     "EVENT_BODY_ATR_MIN": 0.40}),
        ("body045", {"CONTRACT_VR": True, "FADE_PATH": True,
                     "EVENT_BODY_ATR_MIN": 0.45}),
        ("body050", {"CONTRACT_VR": True, "FADE_PATH": True,
                     "EVENT_BODY_ATR_MIN": 0.50}),
    ),
    "cf_cliff_final": (
        ("h4", {"CONTRACT_VR": True, "FADE_PATH": True,
                "VR_HORIZON": 4}),
        ("h5", {"CONTRACT_VR": True, "FADE_PATH": True,
                "VR_HORIZON": 5}),
        ("ratio080", {"CONTRACT_VR": True, "FADE_PATH": True,
                      "VR_CONTRACTION_RATIO_MAX": 0.80}),
        ("path008", {"CONTRACT_VR": True, "FADE_PATH": True,
                     "PATH_EFFICIENCY_MIN": 0.08}),
        ("path012", {"CONTRACT_VR": True, "FADE_PATH": True,
                     "PATH_EFFICIENCY_MIN": 0.12}),
        ("body050", {"CONTRACT_VR": True, "FADE_PATH": True,
                     "EVENT_BODY_ATR_MIN": 0.50}),
    ),
    "path_cliff": (
        ("path005", {"CONTRACT_VR": True, "FADE_PATH": True,
                     "PATH_EFFICIENCY_MIN": 0.05}),
        ("path006", {"CONTRACT_VR": True, "FADE_PATH": True,
                     "PATH_EFFICIENCY_MIN": 0.06}),
        ("path007", {"CONTRACT_VR": True, "FADE_PATH": True,
                     "PATH_EFFICIENCY_MIN": 0.07}),
        ("path008", {"CONTRACT_VR": True, "FADE_PATH": True,
                     "PATH_EFFICIENCY_MIN": 0.08}),
        ("path009", {"CONTRACT_VR": True, "FADE_PATH": True,
                     "PATH_EFFICIENCY_MIN": 0.09}),
        ("path010", {"CONTRACT_VR": True, "FADE_PATH": True,
                     "PATH_EFFICIENCY_MIN": 0.10}),
    ),
}


def _view(summary):
    return {key: summary[key] for key in (
        "closed", "wins", "win_rate", "net_profit", "pnl_per_day",
        "pnl_per_month", "profit_factor", "max_drawdown",
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
        summary, _ = backtest(
            417, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
