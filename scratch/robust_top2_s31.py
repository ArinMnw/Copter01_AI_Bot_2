import sys
sys.path.insert(0, ".")
import MetaTrader5 as mt5
import config
from strategy31 import S31_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as sim

mt5.initialize()
candidates = [("SL1.0_RR1.2", 1.0, 1.2), ("SL1.2_RR1.2", 1.2, 1.2), ("SL1.2_RR1.0(prev_best)", 1.2, 1.0)]
for name, sl, rr in candidates:
    print(f"=== {name} ===")
    for days in [60, 90, 120, 150]:
        entry_bars = s30sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=400)
        htf_bars = s30sim.fetch_bars(config.SYMBOL, "M15", days, extra_bars=200)
        cfg = dict(S31_DEFAULTS); cfg.update(SL_ATR_MULT=sl, TP_RR=rr)
        raw = sim.run_single(entry_bars, htf_bars, cfg, days, 0.20)
        twp, eq = sim.simulate_equity_substream(raw, cfg, sim.START_EQUITY)
        s = s30sim.summarize(twp, eq, cfg["RISK_PCT"], days)
        by_day = sim.daily_series_from_trades(twp)
        c = sim.consistency_metrics(by_day)
        print(f"  {days}d: n={s['trades']} $/d={s['avg_per_day_span']:.2f} $/mo={s['avg_per_day_span']*30:.1f} "
              f"DD={s['max_dd_pct']:.1f}% PF={s['profit_factor']:.2f} posDay={c['pct_pos_days']}% "
              f"maxStreak={c['max_losing_day_streak']}d sharpe={c['sharpe_like']}")
mt5.shutdown()
