import sys
sys.path.insert(0, ".")
import itertools
import time
import MetaTrader5 as mt5
import config
from strategy36 import S36_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim
import sim_s36_backtest as sim

mt5.initialize()
days = 30
entry_bars = s30sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=200)
htf_bars = s30sim.fetch_bars(config.SYMBOL, "M15", days, extra_bars=200)
print(f"entry_bars={len(entry_bars)}")

combos = list(itertools.product(
    [0.15, 0.25],             # MIN_GAP_ATR
    [15],                     # MAX_GAP_AGE_BARS
    [0.3, 0.5, 0.7],          # RETRACE_ENTRY_PCT
    [0.8, 1.0],               # SL_ATR_MULT
    [0.8, 1.0, 1.5],          # TP_RR
))
print(f"total combos: {len(combos)}")
t0 = time.time()
results = []
for i, (mg, ma, rp, sl, rr) in enumerate(combos):
    cfg = dict(S36_DEFAULTS)
    cfg.update(MIN_GAP_ATR=mg, MAX_GAP_AGE_BARS=ma, RETRACE_ENTRY_PCT=rp, SL_ATR_MULT=sl, TP_RR=rr)
    raw = sim.run_single(entry_bars, htf_bars, cfg, days, 0.20)
    twp, eq = s31sim.simulate_equity_substream(raw, cfg, sim.START_EQUITY)
    if (i + 1) % 20 == 0:
        print(f"  progress {i+1}/{len(combos)} elapsed={time.time()-t0:.1f}s", flush=True)
    if not twp or len(twp) < 15:
        continue
    s = s30sim.summarize(twp, eq, cfg["RISK_PCT"], days)
    by_day = s31sim.daily_series_from_trades(twp)
    c = s31sim.consistency_metrics(by_day)
    results.append((mg, ma, rp, sl, rr, s, c))
print(f"done in {time.time()-t0:.1f}s, {len(results)} valid")
mt5.shutdown()

results.sort(key=lambda r: r[6]["sharpe_like"], reverse=True)
print(f"\n{'minGap':>7} {'maxAge':>7} {'retrace':>8} {'sl':>4} {'rr':>4} {'n':>4} {'WR%':>5} "
      f"{'$/mo':>8} {'DD%':>6} {'PF':>5} {'posDay%':>8} {'streak':>7} {'sharpe':>7}")
for mg, ma, rp, sl, rr, s, c in results[:15]:
    print(f"{mg:>7} {ma:>7} {rp:>8} {sl:>4} {rr:>4} {s['trades']:>4} {s['wr']:>5.1f} "
          f"{s['avg_per_day_span']*30:>8.1f} {s['max_dd_pct']:>6.1f} {s['profit_factor']:>5.2f} "
          f"{c['pct_pos_days']:>7.1f}% {c['max_losing_day_streak']:>7} {c['sharpe_like']:>7.3f}")
