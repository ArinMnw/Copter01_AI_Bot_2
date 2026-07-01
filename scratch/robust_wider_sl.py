import sys
sys.path.insert(0, ".")
import MetaTrader5 as mt5
import config
from strategy30 import S30_DEFAULTS
import sim_s30_backtest as sim
from scratch.consistency_s30 import consistency_stats

mt5.initialize()
cfg = dict(S30_DEFAULTS)
cfg.update(ENTRY_PATTERN="engulfing", ENGULF_MIN_RATIO=1.0, SL_ATR_MULT=1.2, TP_RR=1.0,
           MIN_GAP_BARS=1, RISK_PCT=0.5)

for days in [60, 90, 120, 150]:
    entry_bars = sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=400)
    htf_bars = sim.fetch_bars(config.SYMBOL, "M15", days, extra_bars=200)
    htf_series = sim.build_htf_series(htf_bars, cfg)
    raw = sim.replay(entry_bars, htf_series, 0.20, cfg)
    twp, eq = sim.simulate_equity_v2(raw, cfg)
    s = sim.summarize(twp, eq, cfg["RISK_PCT"], days)
    c = consistency_stats(twp, days)
    print(f"{days}d: n={s['trades']} $/d={s['avg_per_day_span']:.2f} "
          f"$/mo={s['avg_per_day_span']*30:.1f} DD={s['max_dd_pct']:.1f}% PF={s['profit_factor']:.2f} "
          f"posDay={c['pct_pos_days']}% maxLoseStreak={c['max_losing_day_streak']}d sharpe={c['sharpe_like']}")
mt5.shutdown()
