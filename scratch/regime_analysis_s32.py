import sys
sys.path.insert(0, ".")
import MetaTrader5 as mt5
import config
from strategy31 import S31_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as sim
from collections import defaultdict

mt5.initialize()
days = 150  # ใช้ window ใหญ่สุดเพื่อความน่าเชื่อถือทางสถิติ
entry_bars = s30sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=400)
htf_bars = s30sim.fetch_bars(config.SYMBOL, "M15", days, extra_bars=200)

cfg = dict(S31_DEFAULTS); cfg.update(SL_ATR_MULT=1.2, TP_RR=1.0)
raw = sim.run_single(entry_bars, htf_bars, cfg, days, 0.20)
twp, eq = sim.simulate_equity_substream(raw, cfg, sim.START_EQUITY)

by_day = sim.daily_series_from_trades(twp)
sorted_days = sorted(by_day.keys())
# หา losing-day-streak (>=2 วันติด) แล้วดูว่าวันที่อยู่ใน streak เป็นวันอะไรของสัปดาห์
import datetime
streak_days = set()
streak = []
for d in sorted_days:
    if by_day[d] < 0:
        streak.append(d)
    else:
        if len(streak) >= 2:
            streak_days.update(streak)
        streak = []
if len(streak) >= 2:
    streak_days.update(streak)

print(f"วันที่อยู่ใน losing-streak (>=2 วันติด): {len(streak_days)} จาก {len(sorted_days)} วันที่มีเทรด")

# weekday breakdown ของ daily pnl ทั้งหมด
wd_pnl = defaultdict(list)
for d, v in by_day.items():
    wd = datetime.datetime.strptime(d, "%Y-%m-%d").weekday()  # 0=Mon
    wd_pnl[wd].append(v)
names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
print("\n=== Daily P&L by weekday (ทุกวันที่มีเทรด) ===")
for wd in range(7):
    vals = wd_pnl.get(wd, [])
    if not vals:
        continue
    pos = sum(1 for v in vals if v > 0)
    print(f"  {names[wd]}: n={len(vals)} sum=${sum(vals):.2f} avg=${sum(vals)/len(vals):.2f} "
          f"posDay={100*pos/len(vals):.1f}%")

# hour-of-day breakdown ของ trade-level pnl (ตาม exit hour, BKK)
hr_pnl = defaultdict(list)
for t in twp:
    hr = config.mt5_ts_to_bkk(t["exit_time_ts"]).hour
    hr_pnl[hr].append(t["pnl_usd"])
print("\n=== Trade P&L by exit hour (BKK) ===")
for hr in sorted(hr_pnl.keys()):
    vals = hr_pnl[hr]
    pos = sum(1 for v in vals if v > 0)
    print(f"  {hr:02d}:00  n={len(vals):>3} sum=${sum(vals):>8.2f} avg=${sum(vals)/len(vals):>6.2f} "
          f"WR={100*pos/len(vals):.1f}%")

mt5.shutdown()
