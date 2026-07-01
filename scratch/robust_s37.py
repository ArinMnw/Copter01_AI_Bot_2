import sys
sys.path.insert(0, ".")
import MetaTrader5 as mt5
import config
from strategy37 import S37_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim
import sim_s37_backtest as sim

mt5.initialize()
cfg = dict(S37_DEFAULTS)
cfg.update(PIVOT_WING=3, MAX_LEVEL_AGE_BARS=60, TOUCH_ATR_MULT=0.3, REJECT_ATR_MULT=0.15,
           SL_ATR_MULT=0.8, TP_RR=1.5)

print(f"config: {cfg['PIVOT_WING']=} {cfg['MAX_LEVEL_AGE_BARS']=} {cfg['TOUCH_ATR_MULT']=} "
      f"{cfg['REJECT_ATR_MULT']=} {cfg['SL_ATR_MULT']=} {cfg['TP_RR']=}")
print(f"{'days':>5} {'n':>5} {'WR%':>5} {'$/mo':>8} {'DD%':>6} {'PF':>5} {'posDay%':>8} {'streak':>7} {'sharpe':>7}")
for days in [30, 45, 60, 90, 120, 150, 180]:
    entry_bars = s30sim.fetch_bars(config.SYMBOL, cfg["ENTRY_TF"], days, extra_bars=cfg["MAX_LEVEL_AGE_BARS"] + 100)
    htf_bars = s30sim.fetch_bars(config.SYMBOL, cfg["HTF_TF"], days, extra_bars=max(cfg["HTF_EMA_PERIOD"], 28) + 60)
    raw = sim.run_single(entry_bars, htf_bars, cfg, days, 0.20)
    twp, eq = s31sim.simulate_equity_substream(raw, cfg, sim.START_EQUITY)
    if not twp:
        print(f"{days:>5} no trades")
        continue
    s = s30sim.summarize(twp, eq, cfg["RISK_PCT"], days)
    by_day = s31sim.daily_series_from_trades(twp)
    c = s31sim.consistency_metrics(by_day)
    print(f"{days:>5} {s['trades']:>5} {s['wr']:>5.1f} {s['avg_per_day_span']*30:>8.1f} "
          f"{s['max_dd_pct']:>6.1f} {s['profit_factor']:>5.2f} {c['pct_pos_days']:>7.1f}% "
          f"{c['max_losing_day_streak']:>7} {c['sharpe_like']:>7.3f}")
mt5.shutdown()
