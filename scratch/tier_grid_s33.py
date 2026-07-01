import sys
sys.path.insert(0, ".")
import MetaTrader5 as mt5
import sim_s33_backtest as s33

mt5.initialize()

TIER_SETS = {
    "loose_5_15 (default)": [(5.0, 1.0), (15.0, 0.7), (100.0, 0.4)],
    "tight_3_8": [(3.0, 1.0), (8.0, 0.6), (100.0, 0.3)],
    "tight_4_10": [(4.0, 1.0), (10.0, 0.6), (100.0, 0.3)],
    "tight_3_8_soft": [(3.0, 1.0), (8.0, 0.7), (100.0, 0.5)],
    "gradual_5tier": [(3.0, 1.0), (6.0, 0.8), (10.0, 0.6), (15.0, 0.4), (100.0, 0.25)],
}

for name, tiers in TIER_SETS.items():
    print(f"=== {name} (combined with circuit_breaker) ===")
    for days in [60, 90, 120, 150]:
        s, c = s33.run_one(days, tiers, use_cb=True)
        if s:
            print(f"  {days}d: n={s['trades']:>4} $/d={s['avg_per_day_span']:>6.2f} "
                  f"$/mo={s['avg_per_day_span']*30:>7.1f} DD={s['max_dd_pct']:>5.1f}% "
                  f"PF={s['profit_factor']:>4.2f} posDay={c['pct_pos_days']:>5.1f}% "
                  f"maxStreak={c['max_losing_day_streak']:>2}d sharpe={c['sharpe_like']:>6.3f}")

mt5.shutdown()
