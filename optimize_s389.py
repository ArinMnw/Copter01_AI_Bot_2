# -*- coding: utf-8 -*-
"""Cross-window falsification and optimization probes for S389."""

import argparse

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = {
    "recent": (2, "2026-07-20T00:00:00+07:00"),
    "h1": (6, "2026-07-01T00:00:00+07:00"),
    "wf": (6, "2026-01-01T00:00:00+07:00"),
    "latest": (2, "2026-07-30T00:00:00+07:00"),
}

GROUPS = {
    "leadlag": (
        ("base", {}),
        ("lead015", {"LEAD_CORR_MIN": 0.15}),
        ("lead035", {"LEAD_CORR_MIN": 0.35}),
        ("lead045", {"LEAD_CORR_MIN": 0.45}),
        ("rise005", {"LEAD_CORR_RISE_MIN": 0.05}),
        ("rise025", {"LEAD_CORR_RISE_MIN": 0.25}),
        ("adv_m050", {"LEAD_ADVANTAGE_MIN": -0.50}),
        ("adv000", {"LEAD_ADVANTAGE_MIN": 0.00}),
        ("flow020", {"DIRECTIONAL_FLOW_MIN": 0.20}),
        ("baseline060", {"BASELINE_BARS": 60}),
        ("baseline100", {"BASELINE_BARS": 100}),
        ("recent020", {"RECENT_BARS": 20}),
        ("recent028", {"RECENT_BARS": 28}),
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
    "breadth": (
        ("base", {}),
        ("path010", {"PATH_EFFICIENCY_MIN": 0.10}),
        ("path025", {"PATH_EFFICIENCY_MIN": 0.25}),
        ("net025", {"NET_MOVE_ATR_MIN": 0.25}),
        ("net050", {"NET_MOVE_ATR_MIN": 0.50}),
        ("body055", {"EVENT_BODY_ATR_MIN": 0.55}),
        ("body075", {"EVENT_BODY_ATR_MIN": 0.75}),
        ("fraction068", {"EVENT_BODY_FRACTION_MIN": 0.68}),
        ("fraction078", {"EVENT_BODY_FRACTION_MIN": 0.78}),
        ("volume100", {"EVENT_VOLUME_RATIO_MIN": 1.00}),
        ("volume120", {"EVENT_VOLUME_RATIO_MIN": 1.20}),
    ),
    "focused": (
        ("lead010", {"LEAD_CORR_MIN": 0.10}),
        ("lead012", {"LEAD_CORR_MIN": 0.12}),
        ("lead015", {"LEAD_CORR_MIN": 0.15}),
        ("lead018", {"LEAD_CORR_MIN": 0.18}),
        ("lead020", {"LEAD_CORR_MIN": 0.20}),
        ("buy_only", {"LEAD_CORR_MIN": 0.15, "ALLOW_SELL": False}),
        ("sell_only", {"LEAD_CORR_MIN": 0.15, "ALLOW_BUY": False}),
        ("rr8", {"LEAD_CORR_MIN": 0.15, "TP_RR": 8.0}),
        ("rr9", {"LEAD_CORR_MIN": 0.15, "TP_RR": 9.0}),
        ("rr10", {"LEAD_CORR_MIN": 0.15, "TP_RR": 10.0}),
        ("rise025", {"LEAD_CORR_MIN": 0.15, "LEAD_CORR_RISE_MIN": 0.25}),
        ("baseline060", {"LEAD_CORR_MIN": 0.15, "BASELINE_BARS": 60}),
    ),
    "final": (
        ("l016_rr10", {"LEAD_CORR_MIN": 0.16, "TP_RR": 10.0}),
        ("l017_rr10", {"LEAD_CORR_MIN": 0.17, "TP_RR": 10.0}),
        ("l018_rr10", {"LEAD_CORR_MIN": 0.18, "TP_RR": 10.0}),
        ("l019_rr10", {"LEAD_CORR_MIN": 0.19, "TP_RR": 10.0}),
        ("l018_rr11", {"LEAD_CORR_MIN": 0.18, "TP_RR": 11.0}),
        ("l018_rr12", {"LEAD_CORR_MIN": 0.18, "TP_RR": 12.0}),
        ("l018_rr14", {"LEAD_CORR_MIN": 0.18, "TP_RR": 14.0}),
        ("l018_rr10_b060", {"LEAD_CORR_MIN": 0.18, "TP_RR": 10.0, "BASELINE_BARS": 60}),
    ),
    "verify": (
        ("l018_rr11", {"LEAD_CORR_MIN": 0.18, "TP_RR": 11.0}),
        ("l019_rr11", {"LEAD_CORR_MIN": 0.19, "TP_RR": 11.0}),
        ("l0195_rr11", {"LEAD_CORR_MIN": 0.195, "TP_RR": 11.0}),
        ("buffer016", {"LEAD_CORR_MIN": 0.19, "TP_RR": 11.0, "SL_BUFFER_ATR": 0.16}),
        ("buffer022", {"LEAD_CORR_MIN": 0.19, "TP_RR": 11.0, "SL_BUFFER_ATR": 0.22}),
        ("be001", {"LEAD_CORR_MIN": 0.19, "TP_RR": 11.0, "BE_RR": 0.01}),
        ("be005", {"LEAD_CORR_MIN": 0.19, "TP_RR": 11.0, "BE_RR": 0.05}),
    ),
    "polish": (
        ("b019", {"LEAD_CORR_MIN": 0.195, "TP_RR": 11.0, "SL_BUFFER_ATR": 0.19}),
        ("b020", {"LEAD_CORR_MIN": 0.195, "TP_RR": 11.0, "SL_BUFFER_ATR": 0.20}),
        ("b021", {"LEAD_CORR_MIN": 0.195, "TP_RR": 11.0, "SL_BUFFER_ATR": 0.21}),
        ("b022", {"LEAD_CORR_MIN": 0.195, "TP_RR": 11.0, "SL_BUFFER_ATR": 0.22}),
        ("b023", {"LEAD_CORR_MIN": 0.195, "TP_RR": 11.0, "SL_BUFFER_ATR": 0.23}),
        ("b024", {"LEAD_CORR_MIN": 0.195, "TP_RR": 11.0, "SL_BUFFER_ATR": 0.24}),
    ),
    "buffer_edge": (
        ("b024", {"LEAD_CORR_MIN": 0.195, "TP_RR": 11.0, "SL_BUFFER_ATR": 0.24}),
        ("b025", {"LEAD_CORR_MIN": 0.195, "TP_RR": 11.0, "SL_BUFFER_ATR": 0.25}),
        ("b026", {"LEAD_CORR_MIN": 0.195, "TP_RR": 11.0, "SL_BUFFER_ATR": 0.26}),
        ("b027", {"LEAD_CORR_MIN": 0.195, "TP_RR": 11.0, "SL_BUFFER_ATR": 0.27}),
        ("b028", {"LEAD_CORR_MIN": 0.195, "TP_RR": 11.0, "SL_BUFFER_ATR": 0.28}),
        ("b030", {"LEAD_CORR_MIN": 0.195, "TP_RR": 11.0, "SL_BUFFER_ATR": 0.30}),
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
            389, months, "M5", 0.20, 0.01, end, 300, cfg, prepared
        )
        print(name, _view(summary), flush=True)


if __name__ == "__main__":
    main()
