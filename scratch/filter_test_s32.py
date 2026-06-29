import sys
sys.path.insert(0, ".")
import MetaTrader5 as mt5
import datetime
import config
from strategy31 import S31_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as sim

mt5.initialize()
BASE = dict(S31_DEFAULTS); BASE.update(SL_ATR_MULT=1.2, TP_RR=1.0)


def filter_trades(twp, exclude_weekday=None, exclude_hours=None):
    out = []
    for t in twp:
        dt = config.mt5_ts_to_bkk(t["fill_time_ts"])
        if exclude_weekday is not None and dt.weekday() == exclude_weekday:
            continue
        if exclude_hours and dt.hour in exclude_hours:
            continue
        out.append(t)
    return out


def run(days, exclude_weekday=None, exclude_hours=None, label=""):
    entry_bars = s30sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=400)
    htf_bars = s30sim.fetch_bars(config.SYMBOL, "M15", days, extra_bars=200)
    raw = sim.run_single(entry_bars, htf_bars, BASE, days, 0.20)
    # apply filter ที่ raw-trade level ก่อนส่งเข้า equity sim (กัน lookahead: filter ใช้แค่เวลาของ
    # ไม้นั้นเอง ไม่ใช้ข้อมูลอนาคต)
    raw_f = filter_trades(raw, exclude_weekday, exclude_hours)
    twp, eq = sim.simulate_equity_substream(raw_f, BASE, sim.START_EQUITY)
    if not twp:
        print(f"  {label} {days}d: no trades")
        return
    s = s30sim.summarize(twp, eq, BASE["RISK_PCT"], days)
    by_day = sim.daily_series_from_trades(twp)
    c = sim.consistency_metrics(by_day)
    print(f"  {label:<20} {days}d: n={s['trades']:>4} $/d={s['avg_per_day_span']:>6.2f} "
          f"$/mo={s['avg_per_day_span']*30:>7.1f} DD={s['max_dd_pct']:>5.1f}% PF={s['profit_factor']:>4.2f} "
          f"posDay={c['pct_pos_days']:>5.1f}% maxStreak={c['max_losing_day_streak']:>2}d sharpe={c['sharpe_like']:>6.3f}")


print("=== baseline (no filter) ===")
for d in [60, 90, 120, 150]:
    run(d, label="baseline")

print("\n=== exclude Friday (weekday=4) ===")
for d in [60, 90, 120, 150]:
    run(d, exclude_weekday=4, label="no-Friday")

print("\n=== exclude hours 15,17,19 (BKK) ===")
for d in [60, 90, 120, 150]:
    run(d, exclude_hours={15, 17, 19}, label="no-15-17-19h")

print("\n=== both: no-Friday + no-15/17/19h ===")
for d in [60, 90, 120, 150]:
    run(d, exclude_weekday=4, exclude_hours={15, 17, 19}, label="both")

mt5.shutdown()
