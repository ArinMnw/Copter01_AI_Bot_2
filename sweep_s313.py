# -*- coding: utf-8 -*-
"""Small robustness sweep for S313's Kendall coupling thresholds."""

from sim_strategy_backtest import backtest, parse_bkk, prepare_rates


END = parse_bkk("2026-07-20T00:00:00+07:00")
PREPARED = prepare_rates(2, "M5", END, 300)


def main():
    results = []
    probes = (
        (0.10, 0.10, 0.20, 0.45),
        (0.10, 0.20, 0.20, 0.45),
        (0.20, 0.10, 0.20, 0.45),
        (0.20, 0.20, 0.20, 0.45),
        (0.20, 0.20, 0.35, 0.45),
        (0.20, 0.20, 0.35, 0.65),
    )
    for tau_min, jump_min, efficiency, body in probes:
        cfg = {
            "RECENT_TAU_MIN": tau_min,
            "TAU_JUMP_MIN": jump_min,
            "PATH_EFFICIENCY_MIN": efficiency,
            "RELEASE_BODY_ATR_MIN": body,
        }
        summary, _ = backtest(
            313, 2, "M5", 0.20, 0.01, END, 300, cfg, PREPARED
        )
        results.append((summary["net_profit"], summary, cfg))
    for net, summary, cfg in sorted(results, reverse=True, key=lambda row: row[0]):
        print(
            f"net={net:8.2f} n={summary['closed']:3d} "
            f"wr={summary['win_rate']} dd={summary['max_drawdown']:7.2f} "
            f"cfg={cfg}"
        )


if __name__ == "__main__":
    main()
