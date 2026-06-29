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
from strategy42 import S42_DEFAULTS
from strategy44 import S44_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim
import sim_s34_backtest as s34sim
import sim_s36_backtest as s36sim
import sim_s37_backtest as s37sim
import sim_s38_backtest as s38sim
import sim_s39_backtest as s39sim
import sim_s40_backtest as s40sim
import sim_s41_backtest as s41sim
import sim_s42_backtest as s42sim
import sim_s44_backtest as s44sim

mt5.initialize()
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
cfg_i = dict(S42_DEFAULTS); cfg_i.update(RANGE_BARS=9, SWEEP_ATR_MULT=0.5, MIN_RANGE_ATR=1.0,
                                          SL_ATR_MULT=1.0, TP_RR=1.0, CONFIRMATION_TYPE="htf_trend")
cfg_k = dict(S44_DEFAULTS); cfg_k.update(LOOKBACK_BARS=80, BUCKET_ATR_MULT=0.2, TOUCH_ATR_MULT=0.5,
                                          REJECT_ATR_MULT=0.15, SL_ATR_MULT=1.0, TP_RR=1.5)

sims = {"a": s31sim, "b": s34sim, "c": s36sim, "d": s37sim, "e": s38sim, "f": s39sim, "g": s40sim,
        "h": s41sim, "i": s42sim, "k": s44sim}
cfgs = {"a": cfg_a, "b": cfg_b, "c": cfg_c, "d": cfg_d, "e": cfg_e, "f": cfg_f, "g": cfg_g,
        "h": cfg_h, "i": cfg_i, "k": cfg_k}

for days in [60, 90, 120, 150, 180]:
    entry_bars = s30sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=600)
    htf_bars = s30sim.fetch_bars(config.SYMBOL, "M15", days, extra_bars=200)

    days_series = {}
    for kk in sims:
        raw = sims[kk].run_single(entry_bars, htf_bars, cfgs[kk], days, 0.20)
        twp, eq = s31sim.simulate_equity_substream(raw, cfgs[kk], s31sim.START_EQUITY)
        days_series[kk] = s31sim.daily_series_from_trades(twp)

    def combine(keys):
        all_days = set()
        for kk in keys:
            all_days |= set(days_series[kk])
        comb = {d: sum(days_series[kk].get(d, 0.0) for kk in keys) for d in all_days}
        c = s31sim.consistency_metrics(comb)
        return sum(comb.values()), c

    total_9, c_9 = combine(list("abcdefghi"))
    total_10, c_10 = combine(list("abcdefghik"))

    print(f"--- {days}d ---")
    print(f"  9-way เดิม : $/mo={total_9/days*30:7.1f} posDay={c_9['pct_pos_days']:5.1f}% "
          f"maxStreak={c_9['max_losing_day_streak']:2}d sharpe={c_9['sharpe_like']:6.3f}")
    print(f"  10-way (+K): $/mo={total_10/days*30:7.1f} posDay={c_10['pct_pos_days']:5.1f}% "
          f"maxStreak={c_10['max_losing_day_streak']:2}d sharpe={c_10['sharpe_like']:6.3f}")
mt5.shutdown()
