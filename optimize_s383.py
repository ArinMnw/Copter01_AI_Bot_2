# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S383."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
}

CORE = {"TAIL_LIFT_RISE_MIN": 0.05}

GROUPS = {
    "tail": (
        ("base", {}),
        ("q055", {"TAIL_QUANTILE": 0.55}),
        ("q065", {"TAIL_QUANTILE": 0.65}),
        ("q070", {"TAIL_QUANTILE": 0.70}),
        ("joint012", {"JOINT_RATE_MIN": 0.12}),
        ("joint015", {"JOINT_RATE_MIN": 0.15}),
        ("lift110", {"TAIL_LIFT_MIN": 1.10}),
        ("lift140", {"TAIL_LIFT_MIN": 1.40}),
        ("rise005", {"TAIL_LIFT_RISE_MIN": 0.05}),
        ("rise020", {"TAIL_LIFT_RISE_MIN": 0.20}),
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
        ("volume090", {"EVENT_VOLUME_RATIO_MIN": 0.90}),
        ("volume115", {"EVENT_VOLUME_RATIO_MIN": 1.15}),
        ("body035", {"EVENT_BODY_ATR_MIN": 0.35}),
        ("body065", {"EVENT_BODY_ATR_MIN": 0.65}),
        ("fraction055", {"EVENT_BODY_FRACTION_MIN": 0.55}),
        ("fraction075", {"EVENT_BODY_FRACTION_MIN": 0.75}),
        ("close065", {"EVENT_CLOSE_FRACTION": 0.65}),
        ("close085", {"EVENT_CLOSE_FRACTION": 0.85}),
    ),
    "focused": (
        ("base", {}),
        ("q055", {"TAIL_QUANTILE": 0.55}),
        ("rise005", {"TAIL_LIFT_RISE_MIN": 0.05}),
        ("core", CORE),
        ("core_direction020", {**CORE, "TAIL_DIRECTIONAL_VOLUME_MIN": 0.20}),
        ("core_path025", {**CORE, "PATH_EFFICIENCY_MIN": 0.25}),
        ("core_volume115", {**CORE, "EVENT_VOLUME_RATIO_MIN": 1.15}),
        ("core_fraction075", {**CORE, "EVENT_BODY_FRACTION_MIN": 0.75}),
    ),
    "windows_risk": (
        ("core", CORE),
        ("baseline060", {**CORE, "BASELINE_BARS": 60}),
        ("baseline100", {**CORE, "BASELINE_BARS": 100}),
        ("recent020", {**CORE, "RECENT_BARS": 20}),
        ("recent024", {**CORE, "RECENT_BARS": 24}),
        ("recent032", {**CORE, "RECENT_BARS": 32}),
        ("buffer006", {**CORE, "SL_BUFFER_ATR": 0.06}),
        ("buffer018", {**CORE, "SL_BUFFER_ATR": 0.18}),
        ("buffer024", {**CORE, "SL_BUFFER_ATR": 0.24}),
    ),
    "local": (
        ("final_core", {**CORE, "SL_BUFFER_ATR": 0.18}),
        ("rise000", {**CORE, "TAIL_LIFT_RISE_MIN": 0.00, "SL_BUFFER_ATR": 0.18}),
        ("rise008", {**CORE, "TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.18}),
        ("rise010", {**CORE, "TAIL_LIFT_RISE_MIN": 0.10, "SL_BUFFER_ATR": 0.18}),
        ("q058", {**CORE, "TAIL_QUANTILE": 0.58, "SL_BUFFER_ATR": 0.18}),
        ("q062", {**CORE, "TAIL_QUANTILE": 0.62, "SL_BUFFER_ATR": 0.18}),
        ("buffer014", {**CORE, "SL_BUFFER_ATR": 0.14}),
        ("buffer016", {**CORE, "SL_BUFFER_ATR": 0.16}),
        ("buffer020", {**CORE, "SL_BUFFER_ATR": 0.20}),
        ("buffer022", {**CORE, "SL_BUFFER_ATR": 0.22}),
        ("maxrisk150", {**CORE, "SL_BUFFER_ATR": 0.18, "MAX_RISK_ATR": 1.50}),
        ("maxrisk200", {**CORE, "SL_BUFFER_ATR": 0.18, "MAX_RISK_ATR": 2.00}),
    ),
    "final": (
        ("core", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.18}),
        ("rise006", {"TAIL_LIFT_RISE_MIN": 0.06, "SL_BUFFER_ATR": 0.18}),
        ("rise007", {"TAIL_LIFT_RISE_MIN": 0.07, "SL_BUFFER_ATR": 0.18}),
        ("rise009", {"TAIL_LIFT_RISE_MIN": 0.09, "SL_BUFFER_ATR": 0.18}),
        ("rise011", {"TAIL_LIFT_RISE_MIN": 0.11, "SL_BUFFER_ATR": 0.18}),
        ("buffer017", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.17}),
        ("buffer019", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.19}),
        ("volume100", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.18, "EVENT_VOLUME_RATIO_MIN": 1.00}),
        ("volume110", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.18, "EVENT_VOLUME_RATIO_MIN": 1.10}),
        ("fraction060", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.18, "EVENT_BODY_FRACTION_MIN": 0.60}),
        ("fraction070", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.18, "EVENT_BODY_FRACTION_MIN": 0.70}),
    ),
    "interaction": (
        ("base", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.18}),
        ("f070", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.18, "EVENT_BODY_FRACTION_MIN": 0.70}),
        ("v110", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.18, "EVENT_VOLUME_RATIO_MIN": 1.10}),
        ("b019", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.19}),
        ("f070_v110", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.18, "EVENT_BODY_FRACTION_MIN": 0.70, "EVENT_VOLUME_RATIO_MIN": 1.10}),
        ("f070_b019", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.19, "EVENT_BODY_FRACTION_MIN": 0.70}),
        ("v110_b019", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.19, "EVENT_VOLUME_RATIO_MIN": 1.10}),
        ("all", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.19, "EVENT_BODY_FRACTION_MIN": 0.70, "EVENT_VOLUME_RATIO_MIN": 1.10}),
        ("all_f068", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.19, "EVENT_BODY_FRACTION_MIN": 0.68, "EVENT_VOLUME_RATIO_MIN": 1.10}),
        ("all_f072", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.19, "EVENT_BODY_FRACTION_MIN": 0.72, "EVENT_VOLUME_RATIO_MIN": 1.10}),
    ),
    "final2": (
        ("all", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.19, "EVENT_BODY_FRACTION_MIN": 0.70, "EVENT_VOLUME_RATIO_MIN": 1.10}),
        ("volume108", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.19, "EVENT_BODY_FRACTION_MIN": 0.70, "EVENT_VOLUME_RATIO_MIN": 1.08}),
        ("volume112", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.19, "EVENT_BODY_FRACTION_MIN": 0.70, "EVENT_VOLUME_RATIO_MIN": 1.12}),
        ("fraction069", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.19, "EVENT_BODY_FRACTION_MIN": 0.69, "EVENT_VOLUME_RATIO_MIN": 1.10}),
        ("fraction071", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.19, "EVENT_BODY_FRACTION_MIN": 0.71, "EVENT_VOLUME_RATIO_MIN": 1.10}),
        ("buffer0185", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.185, "EVENT_BODY_FRACTION_MIN": 0.70, "EVENT_VOLUME_RATIO_MIN": 1.10}),
        ("buffer0195", {"TAIL_LIFT_RISE_MIN": 0.08, "SL_BUFFER_ATR": 0.195, "EVENT_BODY_FRACTION_MIN": 0.70, "EVENT_VOLUME_RATIO_MIN": 1.10}),
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
            383, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
