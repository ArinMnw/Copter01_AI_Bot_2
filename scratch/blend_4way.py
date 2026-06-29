import sys
sys.path.insert(0, ".")
import MetaTrader5 as mt5
import config
from strategy31 import S31_DEFAULTS
from strategy34 import S34_DEFAULTS
from strategy36 import S36_DEFAULTS
from strategy37 import S37_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim
import sim_s34_backtest as s34sim
import sim_s36_backtest as s36sim
import sim_s37_backtest as s37sim

mt5.initialize()
cfg_a = dict(S31_DEFAULTS); cfg_a.update(SL_ATR_MULT=1.2, TP_RR=1.0)
cfg_b = dict(S34_DEFAULTS); cfg_b.update(BREAKOUT_LOOKBACK=8, VOLUME_SURGE_MULT=2.0,
                                          MIN_BREAKOUT_ATR=0.15, SL_ATR_MULT=0.8, TP_RR=1.0)
cfg_c = dict(S36_DEFAULTS); cfg_c.update(MIN_GAP_ATR=0.25, MAX_GAP_AGE_BARS=15,
                                          RETRACE_ENTRY_PCT=0.5, SL_ATR_MULT=1.0, TP_RR=0.8)
cfg_d = dict(S37_DEFAULTS); cfg_d.update(PIVOT_WING=3, MAX_LEVEL_AGE_BARS=60, TOUCH_ATR_MULT=0.3,
                                          REJECT_ATR_MULT=0.15, SL_ATR_MULT=0.8, TP_RR=1.5)

for days in [60, 90, 120, 150, 180]:
    entry_bars = s30sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=600)
    htf_bars = s30sim.fetch_bars(config.SYMBOL, "M15", days, extra_bars=200)

    raw_a = s31sim.run_single(entry_bars, htf_bars, cfg_a, days, 0.20)
    raw_b = s34sim.run_single(entry_bars, htf_bars, cfg_b, days, 0.20)
    raw_c = s36sim.run_single(entry_bars, htf_bars, cfg_c, days, 0.20)
    raw_d = s37sim.run_single(entry_bars, htf_bars, cfg_d, days, 0.20)

    twp_a, eq_a = s31sim.simulate_equity_substream(raw_a, cfg_a, s31sim.START_EQUITY)
    twp_b, eq_b = s31sim.simulate_equity_substream(raw_b, cfg_b, s31sim.START_EQUITY)
    twp_c, eq_c = s31sim.simulate_equity_substream(raw_c, cfg_c, s31sim.START_EQUITY)
    twp_d, eq_d = s31sim.simulate_equity_substream(raw_d, cfg_d, s31sim.START_EQUITY)

    day_a = s31sim.daily_series_from_trades(twp_a)
    day_b = s31sim.daily_series_from_trades(twp_b)
    day_c = s31sim.daily_series_from_trades(twp_c)
    day_d = s31sim.daily_series_from_trades(twp_d)

    days_abc = set(day_a) | set(day_b) | set(day_c)
    comb_abc = {d: day_a.get(d, 0.0) + day_b.get(d, 0.0) + day_c.get(d, 0.0) for d in days_abc}
    c_abc = s31sim.consistency_metrics(comb_abc)
    total_abc = sum(comb_abc.values())

    days_abcd = set(day_a) | set(day_b) | set(day_c) | set(day_d)
    comb_abcd = {d: day_a.get(d, 0.0) + day_b.get(d, 0.0) + day_c.get(d, 0.0) + day_d.get(d, 0.0) for d in days_abcd}
    c_abcd = s31sim.consistency_metrics(comb_abcd)
    total_abcd = sum(comb_abcd.values())

    days_d_only = set(day_d)
    c_d = s31sim.consistency_metrics(day_d)
    total_d = sum(day_d.values())

    print(f"--- {days}d ---")
    print(f"  D only (S/R bounce): $/mo={total_d/days*30:7.1f} posDay={c_d['pct_pos_days']:5.1f}% "
          f"maxStreak={c_d['max_losing_day_streak']:2}d sharpe={c_d['sharpe_like']:6.3f}")
    print(f"  A+B+C (champion เดิม): $/mo={total_abc/days*30:7.1f} posDay={c_abc['pct_pos_days']:5.1f}% "
          f"maxStreak={c_abc['max_losing_day_streak']:2}d sharpe={c_abc['sharpe_like']:6.3f}")
    print(f"  A+B+C+D (4-way)      : $/mo={total_abcd/days*30:7.1f} posDay={c_abcd['pct_pos_days']:5.1f}% "
          f"maxStreak={c_abcd['max_losing_day_streak']:2}d sharpe={c_abcd['sharpe_like']:6.3f}")
mt5.shutdown()
