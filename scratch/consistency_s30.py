"""
scratch/consistency_s30.py — วัด "ความสม่ำเสมอของกำไร" (ไม่ใช่ DD ต่ำสุด/WR สูงสุด) ของ S30 configs
เมตริก: %วันที่กำไรเป็นบวก, max losing-day streak, Sharpe-like (avg/std ของ daily pnl), monthly win-rate
"""
import itertools
import statistics

import MetaTrader5 as mt5

import config
from strategy30 import S30_DEFAULTS
import sim_s30_backtest as sim


def daily_series(trades_with_pnl, days):
    by_day = {}
    for t in trades_with_pnl:
        d = config.mt5_ts_to_bkk(t["exit_time_ts"]).strftime("%Y-%m-%d")
        by_day[d] = by_day.get(d, 0.0) + t["pnl_usd"]
    return by_day


def consistency_stats(trades_with_pnl, days):
    by_day = daily_series(trades_with_pnl, days)
    if not by_day:
        return None
    vals = list(by_day.values())
    pos_days = sum(1 for v in vals if v > 0)
    pct_pos_days = 100.0 * pos_days / len(vals)

    # max consecutive losing days (ตามลำดับวันที่จริง, รวมวันไม่มีเทรดเป็น 0 ไม่ใช่ loss)
    sorted_days = sorted(by_day.keys())
    streak = max_streak = 0
    for d in sorted_days:
        if by_day[d] < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0

    mean_d = statistics.mean(vals)
    std_d = statistics.pstdev(vals) if len(vals) > 1 else 0.0
    sharpe_like = (mean_d / std_d) if std_d > 0 else 0.0

    # monthly buckets (ประมาณ 30 วัน/เดือนจาก span)
    by_month = {}
    for t in trades_with_pnl:
        dt = config.mt5_ts_to_bkk(t["exit_time_ts"])
        key = dt.strftime("%Y-%m")
        by_month[key] = by_month.get(key, 0.0) + t["pnl_usd"]
    months = list(by_month.values())
    pos_months = sum(1 for v in months if v > 0)
    pct_pos_months = 100.0 * pos_months / len(months) if months else 0.0

    return {
        "active_days": len(vals), "pct_pos_days": round(pct_pos_days, 1),
        "max_losing_day_streak": max_streak, "sharpe_like": round(sharpe_like, 3),
        "n_months": len(months), "pct_pos_months": round(pct_pos_months, 1),
        "mean_daily": round(mean_d, 3), "std_daily": round(std_d, 3),
    }


def make_cfg(**over):
    cfg = dict(S30_DEFAULTS)
    cfg.update(over)
    return cfg


CANDIDATES = [
    ("champion_gA003", make_cfg(ENTRY_PATTERN="engulfing", ENGULF_MIN_RATIO=1.0,
                                 SL_ATR_MULT=0.8, TP_RR=1.0, MIN_GAP_BARS=1, RISK_PCT=0.5)),
    ("lower_rr_smoother", make_cfg(ENTRY_PATTERN="engulfing", ENGULF_MIN_RATIO=1.0,
                                    SL_ATR_MULT=0.8, TP_RR=0.6, MIN_GAP_BARS=1, RISK_PCT=0.5)),
    ("higher_rr", make_cfg(ENTRY_PATTERN="engulfing", ENGULF_MIN_RATIO=1.0,
                            SL_ATR_MULT=0.8, TP_RR=1.5, MIN_GAP_BARS=1, RISK_PCT=0.5)),
    ("wider_sl", make_cfg(ENTRY_PATTERN="engulfing", ENGULF_MIN_RATIO=1.0,
                           SL_ATR_MULT=1.2, TP_RR=1.0, MIN_GAP_BARS=1, RISK_PCT=0.5)),
    ("ratio1.3_orig_S29ish", make_cfg(ENTRY_PATTERN="engulfing", ENGULF_MIN_RATIO=1.3,
                                       SL_ATR_MULT=0.8, TP_RR=1.0, MIN_GAP_BARS=1, RISK_PCT=0.5)),
    ("family_freq", make_cfg(ENTRY_PATTERN="family", ENGULF_MIN_RATIO=1.3, STRONG_CLOSE_PCT=0.7,
                              SL_ATR_MULT=0.5, TP_RR=0.8, MIN_GAP_BARS=1, RISK_PCT=0.5)),
    ("more_dd_control_cool20", make_cfg(ENTRY_PATTERN="engulfing", ENGULF_MIN_RATIO=1.0,
                                         SL_ATR_MULT=0.8, TP_RR=1.0, MIN_GAP_BARS=1, RISK_PCT=0.5,
                                         COOLDOWN_TRADES=20)),
    ("trigger2_tighter_cb", make_cfg(ENTRY_PATTERN="engulfing", ENGULF_MIN_RATIO=1.0,
                                      SL_ATR_MULT=0.8, TP_RR=1.0, MIN_GAP_BARS=1, RISK_PCT=0.5,
                                      CONSEC_LOSS_TRIGGER=2, COOLDOWN_TRADES=15)),
]


def main():
    if not mt5.initialize():
        print("MT5 init fail"); return
    days = 120
    entry_bars = sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=400)
    htf_bars = sim.fetch_bars(config.SYMBOL, "M15", days, extra_bars=200)

    print(f"{'label':<26} {'$/d':>7} {'$/mo':>8} {'DD%':>6} {'PF':>5} {'%posDay':>8} "
          f"{'%posMo':>7} {'maxLoseStreak(d)':>17} {'sharpe':>7}")
    results = []
    for label, cfg in CANDIDATES:
        htf_series = sim.build_htf_series(htf_bars, cfg) if cfg["CONFIRMATION_TYPE"] != "none" else None
        raw = sim.replay(entry_bars, htf_series, 0.20, cfg)
        twp, eq = sim.simulate_equity_v2(raw, cfg)
        s = sim.summarize(twp, eq, cfg["RISK_PCT"], days)
        if not s:
            print(f"{label:<26} no trades")
            continue
        c = consistency_stats(twp, days)
        print(f"{label:<26} {s['avg_per_day_span']:>7.2f} {s['avg_per_day_span']*30:>8.1f} "
              f"{s['max_dd_pct']:>6.1f} {s['profit_factor']:>5.2f} {c['pct_pos_days']:>7.1f}% "
              f"{c['pct_pos_months']:>6.1f}% {c['max_losing_day_streak']:>17} {c['sharpe_like']:>7.3f}")
        results.append((label, cfg, s, c))

    mt5.shutdown()
    print("\n=== เรียงด้วย sharpe_like (consistency สูงสุด, ไม่สนใจ DD/WR) ===")
    results.sort(key=lambda r: r[3]["sharpe_like"], reverse=True)
    for label, cfg, s, c in results[:5]:
        print(f"  {label:<26} sharpe={c['sharpe_like']:.3f} %posDay={c['pct_pos_days']:.1f}% "
              f"%posMo={c['pct_pos_months']:.1f}% maxLoseStreak={c['max_losing_day_streak']}d "
              f"$/mo={s['avg_per_day_span']*30:.1f} DD={s['max_dd_pct']:.1f}%")


if __name__ == "__main__":
    main()
