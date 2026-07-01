import sys
sys.path.insert(0, ".")
import itertools
import MetaTrader5 as mt5
import config
from strategy34 import S34_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim
import sim_s34_backtest as sim

mt5.initialize()
days = 45  # ลดวันสำหรับรอบค้นหาเร็วๆ (pure-Python loop ช้าที่ days สูง) ค่อย validate ตัวที่ดีที่สุดที่ 90+
entry_bars = s30sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=600)
htf_bars = s30sim.fetch_bars(config.SYMBOL, "M15", days, extra_bars=200)
print(f"entry_bars={len(entry_bars)} htf_bars={len(htf_bars)}")

results = []
combos = list(itertools.product(
    [8, 20],                  # BREAKOUT_LOOKBACK
    [1.2, 1.5, 2.0],          # VOLUME_SURGE_MULT
    [0.0, 0.15],              # MIN_BREAKOUT_ATR
    [0.8, 1.2],               # SL_ATR_MULT
    [0.8, 1.0, 1.5],          # TP_RR
))
print(f"total combos: {len(combos)}")
import time
t0 = time.time()
for i, (lb, vm, mb, sl, rr) in enumerate(combos):
    cfg = dict(S34_DEFAULTS)
    cfg.update(BREAKOUT_LOOKBACK=lb, VOLUME_SURGE_MULT=vm, MIN_BREAKOUT_ATR=mb,
               SL_ATR_MULT=sl, TP_RR=rr)
    raw = sim.run_single(entry_bars, htf_bars, cfg, days, 0.20)
    twp, eq = s31sim.simulate_equity_substream(raw, cfg, sim.START_EQUITY)
    if (i + 1) % 10 == 0:
        print(f"  progress {i+1}/{len(combos)} elapsed={time.time()-t0:.1f}s", flush=True)
    if not twp or len(twp) < 10:
        continue
    s = s30sim.summarize(twp, eq, cfg["RISK_PCT"], days)
    by_day = s31sim.daily_series_from_trades(twp)
    c = s31sim.consistency_metrics(by_day)
    results.append((lb, vm, mb, sl, rr, s, c))
print(f"done in {time.time()-t0:.1f}s, {len(results)} valid results")

mt5.shutdown()

results.sort(key=lambda r: r[6]["sharpe_like"], reverse=True)
print(f"\n{'lb':>4} {'volM':>5} {'minBO':>6} {'sl':>4} {'rr':>4} {'n':>4} {'WR%':>5} {'$/mo':>8} "
      f"{'DD%':>6} {'PF':>5} {'posDay%':>8} {'streak':>7} {'sharpe':>7}")
for lb, vm, mb, sl, rr, s, c in results[:20]:
    print(f"{lb:>4} {vm:>5} {mb:>6} {sl:>4} {rr:>4} {s['trades']:>4} {s['wr']:>5.1f} "
          f"{s['avg_per_day_span']*30:>8.1f} {s['max_dd_pct']:>6.1f} {s['profit_factor']:>5.2f} "
          f"{c['pct_pos_days']:>7.1f}% {c['max_losing_day_streak']:>7} {c['sharpe_like']:>7.3f}")
