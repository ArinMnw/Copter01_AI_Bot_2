import sys
sys.path.insert(0, ".")
import MetaTrader5 as mt5
import config
from strategy31 import S31_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as sim

mt5.initialize()
for days in [60, 90, 120, 150]:
    entry_bars = s30sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=400)
    htf_bars = s30sim.fetch_bars(config.SYMBOL, "M15", days, extra_bars=200)

    cfg_a = dict(S31_DEFAULTS); cfg_a.update(SL_ATR_MULT=1.2, TP_RR=1.0, SESSIONS=[("14:00", "18:00")])
    cfg_b = dict(S31_DEFAULTS); cfg_b.update(SL_ATR_MULT=1.2, TP_RR=1.0, SESSIONS=[("19:00", "23:00")])

    raw_a = sim.run_single(entry_bars, htf_bars, cfg_a, days, 0.20)
    raw_b = sim.run_single(entry_bars, htf_bars, cfg_b, days, 0.20)
    twp_a, eq_a = sim.simulate_equity_substream(raw_a, cfg_a, sim.START_EQUITY / 2)
    twp_b, eq_b = sim.simulate_equity_substream(raw_b, cfg_b, sim.START_EQUITY / 2)
    day_a = sim.daily_series_from_trades(twp_a)
    day_b = sim.daily_series_from_trades(twp_b)
    all_days = set(day_a) | set(day_b)
    combined = {d: day_a.get(d, 0.0) + day_b.get(d, 0.0) for d in all_days}
    c = sim.consistency_metrics(combined)
    total = sum(combined.values())
    final_eq = eq_a["final_equity"] + eq_b["final_equity"]

    # baseline เทียบ: full session เดิม เต็มทุน $1000 (ไม่แบ่ง)
    cfg_full = dict(S31_DEFAULTS); cfg_full.update(SL_ATR_MULT=1.2, TP_RR=1.0)
    raw_full = sim.run_single(entry_bars, htf_bars, cfg_full, days, 0.20)
    twp_full, eq_full = sim.simulate_equity_substream(raw_full, cfg_full, sim.START_EQUITY)
    day_full = sim.daily_series_from_trades(twp_full)
    c_full = sim.consistency_metrics(day_full)
    total_full = sum(day_full.values())

    print(f"--- {days}d ---")
    print(f"  SESSION-BLEND : $/d={total/days:6.2f} $/mo={total/days*30:7.1f} "
          f"posDay={c['pct_pos_days']:5.1f}% maxStreak={c['max_losing_day_streak']:2}d "
          f"sharpe={c['sharpe_like']:6.3f} final=${final_eq:.2f} n={len(twp_a)+len(twp_b)}")
    print(f"  FULL(no-split): $/d={total_full/days:6.2f} $/mo={total_full/days*30:7.1f} "
          f"posDay={c_full['pct_pos_days']:5.1f}% maxStreak={c_full['max_losing_day_streak']:2}d "
          f"sharpe={c_full['sharpe_like']:6.3f} final=${eq_full['final_equity']:.2f} n={len(twp_full)}")
mt5.shutdown()
