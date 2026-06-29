import sys
sys.path.insert(0, ".")
import MetaTrader5 as mt5
import config
from strategy31 import S31_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as sim

mt5.initialize()
days = 90
entry_bars = s30sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=400)
htf_bars = s30sim.fetch_bars(config.SYMBOL, "M15", days, extra_bars=200)

print(f"{'SL_mult':>8} {'RR':>5} {'n':>5} {'$/d':>7} {'$/mo':>8} {'DD%':>6} {'PF':>5} "
      f"{'posDay%':>8} {'maxStreak':>10} {'sharpe':>7}")
for sl in [0.8, 1.0, 1.2, 1.5, 1.8, 2.2, 2.6]:
    for rr in [0.8, 1.0, 1.2]:
        cfg = dict(S31_DEFAULTS); cfg.update(SL_ATR_MULT=sl, TP_RR=rr)
        raw = sim.run_single(entry_bars, htf_bars, cfg, days, 0.20)
        twp, eq = sim.simulate_equity_substream(raw, cfg, sim.START_EQUITY)
        if not twp:
            continue
        s = s30sim.summarize(twp, eq, cfg["RISK_PCT"], days)
        by_day = sim.daily_series_from_trades(twp)
        c = sim.consistency_metrics(by_day)
        print(f"{sl:>8} {rr:>5} {s['trades']:>5} {s['avg_per_day_span']:>7.2f} "
              f"{s['avg_per_day_span']*30:>8.1f} {s['max_dd_pct']:>6.1f} {s['profit_factor']:>5.2f} "
              f"{c['pct_pos_days']:>7.1f}% {c['max_losing_day_streak']:>10} {c['sharpe_like']:>7.3f}")
mt5.shutdown()
