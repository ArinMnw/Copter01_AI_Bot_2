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

cfg_a = dict(S31_DEFAULTS); cfg_a.update(SL_ATR_MULT=1.2, TP_RR=1.0)
cfg_b = dict(S31_DEFAULTS); cfg_b.update(SL_ATR_MULT=0.8, TP_RR=1.5)

raw_a = sim.run_single(entry_bars, htf_bars, cfg_a, days, 0.20)
raw_b = sim.run_single(entry_bars, htf_bars, cfg_b, days, 0.20)

times_a = {t["signal_time_ts"] for t in raw_a}
times_b = {t["signal_time_ts"] for t in raw_b}
overlap = times_a & times_b
print(f"A signals: {len(times_a)} | B signals: {len(times_b)} | overlap (same bar): {len(overlap)}")
print(f"overlap %% of A: {100*len(overlap)/len(times_a):.1f}% | overlap %% of B: {100*len(overlap)/len(times_b):.1f}%")
mt5.shutdown()
