import sys
sys.path.insert(0, ".")
import MetaTrader5 as mt5
import config
from strategy31 import S31_DEFAULTS
from strategy34 import S34_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim
import sim_s34_backtest as s34sim

mt5.initialize()
days = 150
entry_bars = s30sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=600)
htf_bars = s30sim.fetch_bars(config.SYMBOL, "M15", days, extra_bars=200)

cfg_champ = dict(S31_DEFAULTS); cfg_champ.update(SL_ATR_MULT=1.2, TP_RR=1.0)
cfg_s34 = dict(S34_DEFAULTS); cfg_s34.update(BREAKOUT_LOOKBACK=8, VOLUME_SURGE_MULT=2.0,
                                              MIN_BREAKOUT_ATR=0.15, SL_ATR_MULT=0.8, TP_RR=1.0)

raw_champ = s31sim.run_single(entry_bars, htf_bars, cfg_champ, days, 0.20)
raw_s34 = s34sim.run_single(entry_bars, htf_bars, cfg_s34, days, 0.20)

t_champ = {t["signal_time_ts"] for t in raw_champ}
t_s34 = {t["signal_time_ts"] for t in raw_s34}
overlap = t_champ & t_s34
print(f"champion signals: {len(t_champ)} | S34 signals: {len(t_s34)} | overlap: {len(overlap)}")
print(f"overlap %% of champion: {100*len(overlap)/len(t_champ):.1f}% | overlap %% of S34: {100*len(overlap)/len(t_s34):.1f}%")

print("\n=== sanity-check S34 trades (10 ไม้แรก) ===")
for t in raw_s34[:10]:
    print(f"  {t['signal']:<4} entry={t['entry']:<9} sl={t['sl']:<9} tp={t['tp']:<9} "
          f"outcome={t['outcome']:<3} risk_dist={t['risk_distance']:.3f}")
mt5.shutdown()
