# -*- coding: utf-8 -*-
"""Cross-window local threshold audit for optimized S313."""

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


WINDOWS = (
    ("2m", 2, "2026-07-20T00:00:00+07:00"),
    ("h1", 6, "2026-07-20T00:00:00+07:00"),
    ("wf", 6, "2026-01-20T00:00:00+07:00"),
)
PROBES = (
    ("baseline44", {"BASELINE_BARS": 44}),
    ("baseline52", {"BASELINE_BARS": 52}),
    ("recent14", {"RECENT_BARS": 14}),
    ("recent18", {"RECENT_BARS": 18}),
)


def main():
    prepared = {
        label: (
            months,
            parse_bkk(end),
            prepare_rates(months, "M5", parse_bkk(end), 300),
        )
        for label, months, end in WINDOWS
    }
    for name, override in PROBES:
        cfg = {"BE_RR": 0.05, "TAU_JUMP_MIN": 0.325, **override}
        print(name, cfg, flush=True)
        for label, (months, end, rates) in prepared.items():
            summary, _ = backtest(
                313, months, "M5", 0.20, 0.01, end, 300, cfg, rates
            )
            print(
                label,
                {
                    key: summary[key]
                    for key in (
                        "closed",
                        "wins",
                        "win_rate",
                        "net_profit",
                        "profit_factor",
                        "max_drawdown",
                    )
                },
                flush=True,
            )


if __name__ == "__main__":
    main()
