import sys
sys.path.insert(0, ".")
import MetaTrader5 as mt5
import config
from strategy31 import S31_DEFAULTS
from strategy34 import S34_DEFAULTS
from strategy36 import S36_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim
import sim_s34_backtest as s34sim
import sim_s36_backtest as s36sim

mt5.initialize()
days = 150
entry_bars = s30sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=600)
htf_bars = s30sim.fetch_bars(config.SYMBOL, "M15", days, extra_bars=200)

cfg_a = dict(S31_DEFAULTS); cfg_a.update(SL_ATR_MULT=1.2, TP_RR=1.0)
cfg_b = dict(S34_DEFAULTS); cfg_b.update(BREAKOUT_LOOKBACK=8, VOLUME_SURGE_MULT=2.0,
                                          MIN_BREAKOUT_ATR=0.15, SL_ATR_MULT=0.8, TP_RR=1.0)
cfg_c = dict(S36_DEFAULTS); cfg_c.update(MIN_GAP_ATR=0.25, MAX_GAP_AGE_BARS=15,
                                          RETRACE_ENTRY_PCT=0.5, SL_ATR_MULT=1.0, TP_RR=0.8)

raw_a = s31sim.run_single(entry_bars, htf_bars, cfg_a, days, 0.20)
raw_b = s34sim.run_single(entry_bars, htf_bars, cfg_b, days, 0.20)
raw_c = s36sim.run_single(entry_bars, htf_bars, cfg_c, days, 0.20)

t_a = {t["signal_time_ts"] for t in raw_a}
t_b = {t["signal_time_ts"] for t in raw_b}
t_c = {t["signal_time_ts"] for t in raw_c}
print(f"A(engulfing)={len(t_a)} B(volbreak)={len(t_b)} C(FVG)={len(t_c)}")
print(f"overlap A&C: {len(t_a & t_c)} ({100*len(t_a&t_c)/len(t_c):.1f}% of C)")
print(f"overlap B&C: {len(t_b & t_c)} ({100*len(t_b&t_c)/len(t_c):.1f}% of C)")

print("\n=== sanity-check C (FVG) trades (10 ไม้แรก) ===")
for t in raw_c[:10]:
    print(f"  {t['signal']:<4} entry={t['entry']:<9} sl={t['sl']:<9} tp={t['tp']:<9} "
          f"outcome={t['outcome']:<3} risk_dist={t['risk_distance']:.3f}")
mt5.shutdown()
