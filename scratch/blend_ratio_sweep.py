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
cfg_champ = dict(S31_DEFAULTS); cfg_champ.update(SL_ATR_MULT=1.2, TP_RR=1.0)
cfg_s34 = dict(S34_DEFAULTS); cfg_s34.update(BREAKOUT_LOOKBACK=8, VOLUME_SURGE_MULT=2.0,
                                              MIN_BREAKOUT_ATR=0.15, SL_ATR_MULT=0.8, TP_RR=1.0)

for ratio_champ in [0.3, 0.4, 0.5, 0.6, 0.7]:
    print(f"=== champion={ratio_champ*100:.0f}% / S34={100-ratio_champ*100:.0f}% ===")
    for days in [90, 150]:
        entry_bars = s30sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=600)
        htf_bars = s30sim.fetch_bars(config.SYMBOL, "M15", days, extra_bars=200)
        raw_champ = s31sim.run_single(entry_bars, htf_bars, cfg_champ, days, 0.20)
        raw_s34 = s34sim.run_single(entry_bars, htf_bars, cfg_s34, days, 0.20)
        twp_c, eq_c = s31sim.simulate_equity_substream(raw_champ, cfg_champ, s31sim.START_EQUITY * ratio_champ)
        twp_s, eq_s = s31sim.simulate_equity_substream(raw_s34, cfg_s34, s31sim.START_EQUITY * (1 - ratio_champ))
        day_c = s31sim.daily_series_from_trades(twp_c)
        day_s = s31sim.daily_series_from_trades(twp_s)
        all_days = set(day_c) | set(day_s)
        combined = {d: day_c.get(d, 0.0) + day_s.get(d, 0.0) for d in all_days}
        c = s31sim.consistency_metrics(combined)
        total = sum(combined.values())
        final_eq = eq_c["final_equity"] + eq_s["final_equity"]
        print(f"  {days}d: $/mo={total/days*30:7.1f} posDay={c['pct_pos_days']:5.1f}% "
              f"maxStreak={c['max_losing_day_streak']:2}d sharpe={c['sharpe_like']:6.3f} final=${final_eq:.2f}")
mt5.shutdown()
