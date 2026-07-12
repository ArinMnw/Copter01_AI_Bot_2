import sys
import os
import pandas as pd
import MetaTrader5 as mt5
import argparse
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(r'd:\Project\Copter01_AI_Bot_2'))
import config
from sim_s30_backtest import fetch_bars
import strategy101

parser = argparse.ArgumentParser(description="Backtest S101 HF Liquidity Reversal + Trailing")
parser.add_argument("--days", type=int, default=90)
parser.add_argument("--start", type=str, help="YYYY-MM-DD")
parser.add_argument("--end", type=str, help="YYYY-MM-DD")
parser.add_argument("--fill-bars", type=int, default=20)
parser.add_argument("--cooldown", type=int, default=10)
parser.add_argument("--tf", type=str, default="M5")
parser.add_argument("--out-prefix", type=str, default="s101")
# hyperparameter overrides
parser.add_argument("--disp-atr", type=float, default=None)
parser.add_argument("--disp-atr-stacked", type=float, default=None)
parser.add_argument("--tp-rr", type=float, default=None)
parser.add_argument("--retrace", type=float, default=None)
parser.add_argument("--no-trail", action="store_true")
parser.add_argument("--trail-atr-mult", type=float, default=None)
parser.add_argument("--trail-be-rr", type=float, default=None)
parser.add_argument("--tp-rr-max", type=float, default=None)
parser.add_argument("--no-pdh", action="store_true")
parser.add_argument("--no-eq", action="store_true")
parser.add_argument("--no-time-filter", action="store_true")
args = parser.parse_args()

SYMBOL = "XAUUSD.iux"
TF = args.tf
SPREAD = 0.20
LOOKBACK = 150

if not config.mt5_initialize(mt5):
    print("MT5 init failed")
    sys.exit(1)

if args.start and args.end:
    import pytz
    bkk = pytz.timezone("Asia/Bangkok")
    start_dt = bkk.localize(datetime.strptime(args.start, "%Y-%m-%d"))
    end_dt = bkk.localize(datetime.strptime(args.end, "%Y-%m-%d") + timedelta(days=1))
    tf_map = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15}
    all_bars = mt5.copy_rates_range(SYMBOL, tf_map[TF], start_dt, end_dt)
else:
    all_bars = fetch_bars(SYMBOL, TF, args.days, extra_bars=300)

mt5.shutdown()

if all_bars is None or len(all_bars) == 0:
    print("Failed to fetch")
    sys.exit(1)

cfg_s101 = {}
if args.disp_atr is not None:
    cfg_s101["DISP_BODY_ATR"] = args.disp_atr
if args.disp_atr_stacked is not None:
    cfg_s101["DISP_BODY_ATR_STACKED"] = args.disp_atr_stacked
if args.tp_rr is not None:
    cfg_s101["TP_RR"] = args.tp_rr
if args.retrace is not None:
    cfg_s101["ENTRY_RETRACE"] = args.retrace
if args.no_trail:
    cfg_s101["TRAIL_ENABLED"] = False
if args.trail_atr_mult is not None:
    cfg_s101["TRAIL_ATR_MULT"] = args.trail_atr_mult
if args.trail_be_rr is not None:
    cfg_s101["TRAIL_BE_RR"] = args.trail_be_rr
if args.tp_rr_max is not None:
    cfg_s101["TP_RR_MAX"] = args.tp_rr_max
if args.no_pdh:
    cfg_s101["USE_PDH_PDL"] = False
if args.no_eq:
    cfg_s101["USE_EQ_CLUSTERS"] = False
if args.no_time_filter:
    cfg_s101["TIME_FILTER_ENABLED"] = False


def simulate_trade(direction, entry, sl, tp, trail, bars, fill_idx):
    """จำลองไม้จาก fill bar; trailing แบบ conservative:
    - เช็ค SL ด้วย low/high ของแท่งก่อน (แพ้ก่อนชนะ)
    - อัพเดท trail จาก close ของแท่งที่ปิดแล้วเท่านั้น (มีผลแท่งถัดไป)"""
    cur_sl = sl
    be_done = False
    risk = trail["risk"] if trail else None
    for j in range(fill_idx, len(bars)):
        h, l, cl = bars[j]['high'], bars[j]['low'], bars[j]['close']
        if direction == "BUY":
            if l <= cur_sl:
                return ("SL" if cur_sl <= sl else ("BE" if abs(cur_sl - entry) < 1e-9 else "TRAIL"),
                        cur_sl, j)
            if h >= tp:
                return "TP", tp, j
            if trail:
                if not be_done and cl >= entry + risk * trail["be_rr"]:
                    cur_sl = max(cur_sl, entry)
                    be_done = True
                if be_done:
                    cur_sl = max(cur_sl, cl - trail["atr"] * trail["atr_mult"])
        else:
            if h >= cur_sl:
                return ("SL" if cur_sl >= sl else ("BE" if abs(cur_sl - entry) < 1e-9 else "TRAIL"),
                        cur_sl, j)
            if l <= tp:
                return "TP", tp, j
            if trail:
                if not be_done and cl <= entry - risk * trail["be_rr"]:
                    cur_sl = min(cur_sl, entry)
                    be_done = True
                if be_done:
                    cur_sl = min(cur_sl, cl + trail["atr"] * trail["atr_mult"])
    return None, None, None


trades = []
cancelled = 0
last_trade_idx = -1000

for i in range(LOOKBACK, len(all_bars) - 2):
    if i - last_trade_idx < args.cooldown:
        continue

    rates_slice = all_bars[i - LOOKBACK + 1: i + 1]
    dt_bkk = datetime.fromtimestamp(rates_slice[-1]['time'])
    sig = strategy101.detect_s101(rates_slice, tf=TF, dt_bkk=dt_bkk, cfg=cfg_s101)

    if not sig or sig.get("signal") not in ("BUY", "SELL"):
        continue

    direction = sig["signal"]
    entry, sl, tp = sig["entry"], sig["sl"], sig["tp"]
    trail = sig.get("trail")
    signal_time = datetime.fromtimestamp(all_bars[i]['time'])

    fill_idx = None
    for j in range(i + 1, min(i + 1 + args.fill_bars, len(all_bars))):
        h, l = all_bars[j]['high'], all_bars[j]['low']
        if (direction == "BUY" and l <= entry - SPREAD) or (direction == "SELL" and h >= entry + SPREAD):
            fill_idx = j
            break

    if fill_idx is None:
        cancelled += 1
        last_trade_idx = i
        continue

    outcome, exit_price, exit_idx = simulate_trade(
        direction, entry, sl, tp, trail, all_bars, fill_idx)
    if outcome is None:
        continue

    last_trade_idx = i
    diff = (exit_price - entry) if direction == "BUY" else (entry - exit_price)
    usd = diff - SPREAD
    trades.append({
        'time': signal_time.strftime('%Y-%m-%d %H:%M'),
        'fill_time': datetime.fromtimestamp(all_bars[fill_idx]['time']).strftime('%Y-%m-%d %H:%M'),
        'exit_time': datetime.fromtimestamp(all_bars[exit_idx]['time']).strftime('%Y-%m-%d %H:%M'),
        'dir': direction,
        'entry': round(entry, 2),
        'sl': round(sl, 2),
        'tp': round(tp, 2),
        'outcome': outcome,
        'profit': round(usd, 2),
        'reason': sig.get('reason', ''),
    })

df = pd.DataFrame(trades)
df.to_csv(f"{args.out_prefix}_trades.csv", index=False)

n = len(df)
print(f"Signals filled: {n} | Cancelled (no fill): {cancelled}")
if n > 0:
    wins = (df['profit'] > 0).sum()
    losses = (df['profit'] < 0).sum()
    net = df['profit'].sum()
    wr = wins / (wins + losses) * 100 if wins + losses else 0
    gw = df.loc[df['profit'] > 0, 'profit'].sum()
    gl = -df.loc[df['profit'] < 0, 'profit'].sum()
    pf = gw / gl if gl > 0 else float('inf')
    by_outcome = df['outcome'].value_counts().to_dict()
    print(f"Win {wins} | Loss {losses} | WinRate {wr:.1f}% | Net {net:.2f} USD | PF {pf:.2f}")
    print(f"Outcomes: {by_outcome}")

    df['time'] = pd.to_datetime(df['time'])
    monthly = df.groupby(df['time'].dt.strftime('%Y-%m'))['profit'].agg(['count', 'sum'])
    print(" | ".join(f"{m}: n={int(r['count'])} {r['sum']:+.0f}" for m, r in monthly.iterrows()))

    df['date'] = df['time'].dt.date
    daily = df.groupby('date')['profit'].agg(['count', 'sum']).reset_index()
    daily.columns = ['date', 'trades', 'net_profit']
    daily.to_csv(f"{args.out_prefix}_daily.csv", index=False)
    neg_days = (daily['net_profit'] < 0).sum()
    print(f"Days: {len(daily)} | Negative days: {neg_days} | Avg/day {daily['net_profit'].mean():.2f}")
