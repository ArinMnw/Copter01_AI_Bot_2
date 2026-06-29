import sys
sys.path.insert(0, ".")
import MetaTrader5 as mt5
import config
from strategy31 import S31_DEFAULTS
from strategy34 import S34_DEFAULTS
from strategy36 import S36_DEFAULTS
from strategy37 import S37_DEFAULTS
from strategy38 import S38_DEFAULTS
from strategy39 import S39_DEFAULTS
from strategy40 import S40_DEFAULTS
from strategy41 import S41_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim
import sim_s34_backtest as s34sim
import sim_s36_backtest as s36sim
import sim_s37_backtest as s37sim
import sim_s38_backtest as s38sim
import sim_s39_backtest as s39sim
import sim_s40_backtest as s40sim
import sim_s41_backtest as s41sim

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
cfg_f = dict(S39_DEFAULTS); cfg_f.update(BASE_BARS=3, BASE_ATR_MULT=1.5, IMPULSE_ATR_MULT=0.8,
                                          MAX_ZONE_AGE_BARS=30, SL_ATR_MULT=0.8, TP_RR=1.5)
cfg_g = dict(S40_DEFAULTS); cfg_g.update(ZIGZAG_MIN_ATR=1.5, ZIGZAG_LOOKBACK_BARS=200, MAX_WAVE4_AGE_BARS=25,
                                          ENTRY_BREAK_ATR_MULT=0.1, SL_ATR_MULT=1.0, TP_RR=1.5)
cfg_h = dict(S41_DEFAULTS); cfg_h.update(PIVOT_WING=2, MIN_PRICE_DIFF_ATR=0.3, MIN_RSI_DIFF=3.0,
                                          MAX_CONFIRM_AGE_BARS=8, SL_ATR_MULT=0.8, TP_RR=1.0,
                                          CONFIRMATION_TYPE="htf_trend")

raws = {
    "a": s31sim.run_single(entry_bars, htf_bars, cfg_a, days, 0.20),
    "b": s34sim.run_single(entry_bars, htf_bars, cfg_b, days, 0.20),
    "c": s36sim.run_single(entry_bars, htf_bars, cfg_c, days, 0.20),
    "d": s37sim.run_single(entry_bars, htf_bars, cfg_d, days, 0.20),
    "e": s38sim.run_single(entry_bars, htf_bars, cfg_e, days, 0.20),
    "f": s39sim.run_single(entry_bars, htf_bars, cfg_f, days, 0.20),
    "g": s40sim.run_single(entry_bars, htf_bars, cfg_g, days, 0.20),
    "h": s41sim.run_single(entry_bars, htf_bars, cfg_h, days, 0.20),
}
t_h = {t["signal_time_ts"] for t in raws["h"]}
print(f"H(RSI div)={len(t_h)}")
for k in "abcdefg":
    t_k = {t["signal_time_ts"] for t in raws[k]}
    ov = len(t_k & t_h)
    pct = 100*ov/len(t_h) if t_h else 0
    print(f"overlap {k.upper()}&H: {ov} ({pct:.1f}% of H)")

print("\n=== sanity-check H (RSI divergence) ===")
bad = 0
for t in raws["h"]:
    ok = (t["sl"] < t["entry"] < t["tp"]) if t["signal"] == "BUY" else (t["tp"] < t["entry"] < t["sl"])
    if not ok:
        bad += 1
print(f"bad trades total: {bad}/{len(raws['h'])}")
mt5.shutdown()
