import sys
sys.path.insert(0, ".")
import MetaTrader5 as mt5
import sim_s33_backtest as s33

mt5.initialize()
TIER_SETS = {
    "flat (no dd-sizing, CB only)": [(100.0, 1.0)],
    "tight_3_8": [(3.0, 1.0), (8.0, 0.6), (100.0, 0.3)],
    "gradual_5tier": [(3.0, 1.0), (6.0, 0.8), (10.0, 0.6), (15.0, 0.4), (100.0, 0.25)],
}
for risk_pct in [2.0, 5.0]:
    print(f"\n########## base RISK_PCT = {risk_pct}% ##########")
    for name, tiers in TIER_SETS.items():
        print(f"=== {name} ===")
        for days in [60, 90, 120, 150]:
            s, c = s33.run_one(days, tiers, use_cb=True, risk_pct=risk_pct)
            if s:
                print(f"  {days}d: n={s['trades']:>4} lot={s['lot_min']}-{s['lot_max']} "
                      f"$/d={s['avg_per_day_span']:>7.2f} $/mo={s['avg_per_day_span']*30:>8.1f} "
                      f"DD={s['max_dd_pct']:>5.1f}% PF={s['profit_factor']:>4.2f} "
                      f"posDay={c['pct_pos_days']:>5.1f}% maxStreak={c['max_losing_day_streak']:>2}d "
                      f"sharpe={c['sharpe_like']:>6.3f}")
mt5.shutdown()
