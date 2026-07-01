"""
optimize_s28.py — Grid search สำหรับ S28 (Asian Range Liquidity Sweep) ตามกฎข้อ 2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESEARCH / BACKTEST-ONLY

>= 50 combinations ที่มีความหมาย:
  Group A: baseline sweep params x RR (M1/M5)      = 2×3×2×2×4 = 96
  Group B: RSI filter                                = 8
  Group C: Momentum filter                           = 6
  Group D: Leverage scaling test                     = 6
  Group E: Max trades per day                        = 6
  Group F: M15 TF                                    = 6
  Group G: Combined RSI + Momentum                   = 4
  Group H: Tight session window (London/NY only)     = 4
  Total = ~136 combinations
"""

import sys
import time as _time

import MetaTrader5 as mt5

import config
from strategy28 import S28_DEFAULTS
import sim_s28_backtest as sim

DAYS = 30
SPREAD = 0.20


def main():
    if not mt5.initialize():
        print(f"MT5 initialize failed: {mt5.last_error()}")
        return

    symbol = config.SYMBOL
    print(f"=== S28 grid search | symbol={symbol} | days={DAYS} ===")

    bars_cache = {}
    for etf in ("M1", "M5", "M15"):
        bars = sim.fetch_bars(symbol, etf, DAYS, extra_bars=1500)
        bars_cache[etf] = bars
        print(f"  fetched {etf}: {len(bars) if bars is not None else 0} bars")

    mt5.shutdown()

    results = []

    def run_one(cfg, label, etf):
        t0 = _time.time()
        bars = bars_cache[etf]
        if bars is None:
            print(f"[{label}] no bars for {etf}")
            return None
        cfg["ENTRY_TF"] = etf
        raw = sim.replay(bars, SPREAD, cfg)
        trades_with_pnl, equity_stats = sim.simulate_equity(raw, cfg["RISK_PCT"])
        s = sim.summarize(trades_with_pnl, equity_stats, cfg["RISK_PCT"], DAYS)
        dt = _time.time() - t0
        if s:
            sim.append_summary_csv(label, s, cfg, cfg["RISK_PCT"])
            print(f"[{label}] {sim.fmt_summary(s)}  ({dt:.1f}s)")
        else:
            print(f"[{label}] no trades  ({dt:.1f}s)")
        results.append((label, cfg.copy(), s))
        return s

    combo_idx = 0

    # ═══════════════════════════════════════════════════════════════
    # Group A: Baseline — sweep_min x body_rev x SL x RR (M1/M5)
    # ═══════════════════════════════════════════════════════════════
    for etf in ("M1", "M5"):
        for sweep_min in (0.02, 0.05, 0.15):
            for body_rev in (0.2, 0.4):
                for sl in (0.2, 0.5):
                    for rr in (1.0, 1.5, 2.0, 3.0):
                        combo_idx += 1
                        cfg = dict(S28_DEFAULTS)
                        cfg["SWEEP_MIN_ATR"] = sweep_min
                        cfg["BODY_REVERSAL_PCT"] = body_rev
                        cfg["SL_ATR_MULT"] = sl
                        cfg["TP_RR"] = rr
                        run_one(cfg, f"g{combo_idx:03d}_A_{etf}_sw{sweep_min}_br{body_rev}_sl{sl}_rr{rr}", etf)

    # ═══════════════════════════════════════════════════════════════
    # Group B: RSI filter ON (M5)
    # ═══════════════════════════════════════════════════════════════
    for sweep_min in (0.02, 0.05):
        for rr in (1.5, 2.0):
            for rsi_ob in (65, 70):
                combo_idx += 1
                cfg = dict(S28_DEFAULTS)
                cfg["SWEEP_MIN_ATR"] = sweep_min
                cfg["RSI_FILTER"] = True
                cfg["RSI_OB"] = rsi_ob
                cfg["RSI_OS"] = 100 - rsi_ob
                cfg["TP_RR"] = rr
                run_one(cfg, f"g{combo_idx:03d}_B_rsi_sw{sweep_min}_rr{rr}_ob{rsi_ob}", "M5")

    # ═══════════════════════════════════════════════════════════════
    # Group C: Momentum filter ON (M5)
    # ═══════════════════════════════════════════════════════════════
    for mom_body in (0.3, 0.5, 0.7):
        for rr in (1.5, 2.0):
            combo_idx += 1
            cfg = dict(S28_DEFAULTS)
            cfg["MOMENTUM_FILTER"] = True
            cfg["MOM_BODY_ATR"] = mom_body
            cfg["TP_RR"] = rr
            run_one(cfg, f"g{combo_idx:03d}_C_mom_mb{mom_body}_rr{rr}", "M5")

    # ═══════════════════════════════════════════════════════════════
    # Group D: Higher risk % (leverage scaling test per Rule 3)
    # ═══════════════════════════════════════════════════════════════
    for risk in (3.0, 5.0, 8.0):
        for rr in (1.5, 2.0):
            combo_idx += 1
            cfg = dict(S28_DEFAULTS)
            cfg["RISK_PCT"] = risk
            cfg["TP_RR"] = rr
            run_one(cfg, f"g{combo_idx:03d}_D_risk_r{risk}_rr{rr}", "M5")

    # ═══════════════════════════════════════════════════════════════
    # Group E: Max trades per day variation (M5)
    # ═══════════════════════════════════════════════════════════════
    for maxday in (1, 2, 5, 15):
        for rr in (1.5, 2.0):
            combo_idx += 1
            cfg = dict(S28_DEFAULTS)
            cfg["MAX_TRADES_PER_DAY"] = maxday
            cfg["TP_RR"] = rr
            run_one(cfg, f"g{combo_idx:03d}_E_maxday_d{maxday}_rr{rr}", "M5")

    # ═══════════════════════════════════════════════════════════════
    # Group F: M15 entry TF (larger TF sweeps)
    # ═══════════════════════════════════════════════════════════════
    for sweep_min in (0.02, 0.1):
        for rr in (1.5, 2.0, 3.0):
            combo_idx += 1
            cfg = dict(S28_DEFAULTS)
            cfg["SWEEP_MIN_ATR"] = sweep_min
            cfg["TP_RR"] = rr
            run_one(cfg, f"g{combo_idx:03d}_F_M15_sw{sweep_min}_rr{rr}", "M15")

    # ═══════════════════════════════════════════════════════════════
    # Group G: Combined RSI + Momentum (M5)
    # ═══════════════════════════════════════════════════════════════
    for rr in (1.5, 2.0):
        for rsi_ob in (65, 70):
            combo_idx += 1
            cfg = dict(S28_DEFAULTS)
            cfg["RSI_FILTER"] = True
            cfg["RSI_OB"] = rsi_ob
            cfg["RSI_OS"] = 100 - rsi_ob
            cfg["MOMENTUM_FILTER"] = True
            cfg["MOM_BODY_ATR"] = 0.3
            cfg["TP_RR"] = rr
            run_one(cfg, f"g{combo_idx:03d}_G_combo_rr{rr}_ob{rsi_ob}", "M5")

    # ═══════════════════════════════════════════════════════════════
    # Group H: Tight session windows (M5)
    # ═══════════════════════════════════════════════════════════════
    sessions = [
        (14, 0, 20, 0, "london"),       # London only
        (19, 30, 23, 0, "ny"),           # NY only
        (14, 0, 23, 0, "london_ny"),     # London+NY
        (11, 0, 16, 0, "pre_london"),    # Pre-London to mid-London
    ]
    for start_h, start_m, end_h, end_m, sess_name in sessions:
        combo_idx += 1
        cfg = dict(S28_DEFAULTS)
        cfg["TRADE_START_H"] = start_h
        cfg["TRADE_START_M"] = start_m
        cfg["TRADE_END_H"] = end_h
        cfg["TRADE_END_M"] = end_m
        cfg["TP_RR"] = 2.0
        run_one(cfg, f"g{combo_idx:03d}_H_sess_{sess_name}_rr2", "M5")

    print(f"\n=== Total {combo_idx} combinations ===")

    # ── Summary ──
    valid = [(lbl, c, s) for lbl, c, s in results if s]
    if not valid:
        print("No valid results!")
        return

    print(f"\nTotal valid: {len(valid)}/{combo_idx}")

    valid.sort(key=lambda x: x[2]["avg_per_day_span"], reverse=True)
    print("\nTop 10 by avg_per_day_span:")
    for lbl, c, s in valid[:10]:
        print(f"  {lbl}: avg/day(span)=${s['avg_per_day_span']:.2f} WR={s['wr']}% "
              f"trades/day={s['trades_per_active_day']} PF={s['profit_factor']} "
              f"avgR={s['avg_r_multiple']} maxDD={s['max_dd_pct']:.1f}% risk={s['risk_pct']}%")

    valid.sort(key=lambda x: x[2]["profit_factor"], reverse=True)
    print("\nTop 10 by profit_factor:")
    for lbl, c, s in valid[:10]:
        print(f"  {lbl}: PF={s['profit_factor']} avg/day(span)=${s['avg_per_day_span']:.2f} WR={s['wr']}% "
              f"trades/day={s['trades_per_active_day']} avgR={s['avg_r_multiple']} risk={s['risk_pct']}%")

    # Best by avg_r_multiple (true edge metric)
    valid.sort(key=lambda x: x[2]["avg_r_multiple"], reverse=True)
    print("\nTop 10 by avg_r_multiple (edge metric):")
    for lbl, c, s in valid[:10]:
        print(f"  {lbl}: avgR={s['avg_r_multiple']} PF={s['profit_factor']} WR={s['wr']}% "
              f"avg/day=${s['avg_per_day_span']:.2f} risk={s['risk_pct']}%")


if __name__ == "__main__":
    main()
