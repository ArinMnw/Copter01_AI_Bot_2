import sys
sys.path.insert(0, ".")
import itertools
import time
import MetaTrader5 as mt5
import config
from strategy47 import S47_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim
import sim_s47_backtest as sim

mt5.initialize()
days = 90
cfg0 = dict(S47_DEFAULTS)
entry_bars = s30sim.fetch_bars(config.SYMBOL, cfg0["ENTRY_TF"], days, extra_bars=200)
htf_bars = s30sim.fetch_bars(config.SYMBOL, cfg0["HTF_TF"], days, extra_bars=200)
print(f"entry_bars={len(entry_bars)}")

combos = list(itertools.product(
    [10, 20],          # ST_ATR_PERIOD
    [2.0, 2.5],         # ST_ATR_MULT
    [0.8, 1.0, 1.5],     # SL_ATR_MULT
    [1.0, 1.5, 2.0],     # TP_RR
    [False, True],      # SESSION_FILTER
))
print(f"total combos: {len(combos)}")
t0 = time.time()
results = []
for i, (period, mult, sl, rr, sess) in enumerate(combos):
    cfg = dict(S47_DEFAULTS)
    cfg.update(ST_ATR_PERIOD=period, ST_ATR_MULT=mult, SL_ATR_MULT=sl, TP_RR=rr,
               SESSION_FILTER=sess, CONFIRMATION_TYPE="htf_trend")
    raw = sim.run_single(entry_bars, htf_bars, cfg, days, 0.20)
    twp, eq = s31sim.simulate_equity_substream(raw, cfg, sim.START_EQUITY)
    if (i + 1) % 20 == 0:
        print(f"  progress {i+1}/{len(combos)} elapsed={time.time()-t0:.1f}s", flush=True)
    if not twp or len(twp) < 15:
        continue
    s = s30sim.summarize(twp, eq, cfg["RISK_PCT"], days)
    by_day = s31sim.daily_series_from_trades(twp)
    c = s31sim.consistency_metrics(by_day)
    results.append((period, mult, sl, rr, sess, s, c))
print(f"done in {time.time()-t0:.1f}s, {len(results)} valid")
mt5.shutdown()

results.sort(key=lambda r: r[6]["sharpe_like"], reverse=True)
print(f"\n{'period':>6} {'mult':>5} {'sl':>4} {'rr':>4} {'sess':>5} {'n':>4} {'WR%':>5} "
      f"{'$/mo':>8} {'DD%':>6} {'PF':>5} {'posDay%':>8} {'streak':>7} {'sharpe':>7}")
for period, mult, sl, rr, sess, s, c in results[:15]:
    print(f"{period:>6} {mult:>5} {sl:>4} {rr:>4} {str(sess):>5} {s['trades']:>4} {s['wr']:>5.1f} "
          f"{s['avg_per_day_span']*30:>8.1f} {s['max_dd_pct']:>6.1f} {s['profit_factor']:>5.2f} "
          f"{c['pct_pos_days']:>7.1f}% {c['max_losing_day_streak']:>7} {c['sharpe_like']:>7.3f}")
