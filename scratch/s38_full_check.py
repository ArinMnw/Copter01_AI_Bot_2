import sys
sys.path.insert(0, ".")
import MetaTrader5 as mt5
import config
from strategy31 import S31_DEFAULTS
from strategy34 import S34_DEFAULTS
from strategy36 import S36_DEFAULTS
from strategy37 import S37_DEFAULTS
from strategy38 import S38_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim
import sim_s34_backtest as s34sim
import sim_s36_backtest as s36sim
import sim_s37_backtest as s37sim
import sim_s38_backtest as s38sim

mt5.initialize()
days = 150
entry_bars = s30sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=600)
htf_bars = s30sim.fetch_bars(config.SYMBOL, "M15", days, extra_bars=200)

cfg_a = dict(S31_DEFAULTS); cfg_a.update(SL_ATR_MULT=1.2, TP_RR=1.0)
cfg_b = dict(S34_DEFAULTS); cfg_b.update(BREAKOUT_LOOKBACK=8, VOLUME_SURGE_MULT=2.0,
                                          MIN_BREAKOUT_ATR=0.15, SL_ATR_MULT=0.8, TP_RR=1.0)
cfg_c = dict(S36_DEFAULTS); cfg_c.update(MIN_GAP_ATR=0.25, MAX_GAP_AGE_BARS=15,
                                          RETRACE_ENTRY_PCT=0.5, SL_ATR_MULT=1.0, TP_RR=0.8)
cfg_d = dict(S37_DEFAULTS); cfg_d.update(PIVOT_WING=3, MAX_LEVEL_AGE_BARS=60, TOUCH_ATR_MULT=0.3,
                                          REJECT_ATR_MULT=0.15, SL_ATR_MULT=0.8, TP_RR=1.5)
cfg_e = dict(S38_DEFAULTS); cfg_e.update(SWING_LOOKBACK_BARS=25, MIN_SWING_ATR=3.0,
                                          MAX_RETRACE_AGE_BARS=20, SL_ATR_MULT=1.0, TP_RR=1.0)

raw_a = s31sim.run_single(entry_bars, htf_bars, cfg_a, days, 0.20)
raw_b = s34sim.run_single(entry_bars, htf_bars, cfg_b, days, 0.20)
raw_c = s36sim.run_single(entry_bars, htf_bars, cfg_c, days, 0.20)
raw_d = s37sim.run_single(entry_bars, htf_bars, cfg_d, days, 0.20)
raw_e = s38sim.run_single(entry_bars, htf_bars, cfg_e, days, 0.20)

t_a = {t["signal_time_ts"] for t in raw_a}
t_b = {t["signal_time_ts"] for t in raw_b}
t_c = {t["signal_time_ts"] for t in raw_c}
t_d = {t["signal_time_ts"] for t in raw_d}
t_e = {t["signal_time_ts"] for t in raw_e}
print(f"A={len(t_a)} B={len(t_b)} C={len(t_c)} D={len(t_d)} E(OTE)={len(t_e)}")
print(f"overlap A&E: {len(t_a & t_e)} ({100*len(t_a&t_e)/len(t_e):.1f}% of E)")
print(f"overlap B&E: {len(t_b & t_e)} ({100*len(t_b&t_e)/len(t_e):.1f}% of E)")
print(f"overlap C&E: {len(t_c & t_e)} ({100*len(t_c&t_e)/len(t_e):.1f}% of E)")
print(f"overlap D&E: {len(t_d & t_e)} ({100*len(t_d&t_e)/len(t_e):.1f}% of E)")
mt5.shutdown()
