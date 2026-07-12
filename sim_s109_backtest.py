import sys
import os
import pandas as pd
import MetaTrader5 as mt5
import argparse
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(r'd:\Project\Copter01_AI_Bot_2'))
import config
from sim_s30_backtest import fetch_bars
import strategy109

parser = argparse.ArgumentParser(description="Backtest S109 Harmonic Fibonacci Sniper")
parser.add_argument("--days", type=int, default=90)
parser.add_argument("--start", type=str, help="YYYY-MM-DD")
parser.add_argument("--end", type=str, help="YYYY-MM-DD")
parser.add_argument("--fill-bars", type=int, default=144, help="Cancel limit if not filled within N bars")
parser.add_argument("--cooldown", type=int, default=60, help="Bars between trades")
parser.add_argument("--tf", type=str, default="M5")
parser.add_argument("--out-prefix", type=str, default="s109")
# hyperparameter overrides
parser.add_argument("--disp-atr", type=float, default=None)
parser.add_argument("--tp-rr", type=float, default=None)
parser.add_argument("--retrace", type=float, default=None)
parser.add_argument("--sl-buf", type=float, default=None)
parser.add_argument("--rsi-buy-min", type=float, default=None)
parser.add_argument("--rsi-sell-max", type=float, default=None)
parser.add_argument("--htf-span", type=int, default=None)
parser.add_argument("--mtf-span", type=int, default=None)
parser.add_argument("--macd", action="store_true")
parser.add_argument("--no-rsi-slope", action="store_true")
parser.add_argument("--no-time-filter", action="store_true")
args = parser.parse_args()

SYMBOL = "XAUUSD.iux"
TF = args.tf
SPREAD = 0.20
LOOKBACK = 660  # ต้อง >= HTF_EMA_SPAN + 30

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
    all_bars = fetch_bars(SYMBOL, TF, args.days, extra_bars=800)

mt5.shutdown()

if all_bars is None or len(all_bars) == 0:
    print("Failed to fetch")
    sys.exit(1)

cfg_s109 = {}
if args.disp_atr is not None:
    cfg_s109["DISP_BODY_ATR"] = args.disp_atr
if args.tp_rr is not None:
    cfg_s109["TP_RR"] = args.tp_rr
if args.retrace is not None:
    cfg_s109["ENTRY_RETRACE"] = args.retrace
if args.sl_buf is not None:
    cfg_s109["SL_BUF_ATR"] = args.sl_buf
if args.rsi_buy_min is not None:
    cfg_s109["RSI_BUY_MIN"] = args.rsi_buy_min
if args.rsi_sell_max is not None:
    cfg_s109["RSI_SELL_MAX"] = args.rsi_sell_max
if args.htf_span is not None:
    cfg_s109["HTF_EMA_SPAN"] = args.htf_span
if args.mtf_span is not None:
    cfg_s109["MTF_EMA_SPAN"] = args.mtf_span
if args.macd:
    cfg_s109["MACD_CONFIRM"] = True
if args.no_rsi_slope:
    cfg_s109["RSI_SLOPE_CONFIRM"] = False
if args.no_time_filter:
    cfg_s109["TIME_FILTER_ENABLED"] = False

trades = []
cancelled = 0
last_trade_idx = -1000

for i in range(LOOKBACK, len(all_bars) - 2):
    if i - last_trade_idx < args.cooldown:
        continue

    rates_slice = all_bars[i - LOOKBACK + 1: i + 1]
    dt_bkk = datetime.fromtimestamp(rates_slice[-1]['time'])
    sig = strategy109.detect_s109(rates_slice, tf=TF, dt_bkk=dt_bkk, cfg=cfg_s109)

    if not sig or sig.get("signal") not in ("BUY", "SELL"):
        continue

    direction = sig["signal"]
    entry, sl, tp = sig["entry"], sig["sl"], sig["tp"]
    signal_time = datetime.fromtimestamp(all_bars[i]['time'])

    # --- Phase 1: wait for limit fill ---
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

    # --- Phase 2: simulate TP/SL from fill bar (conservative: SL first on fill bar) ---
    outcome = "OPEN"
    exit_price = 0
    exit_time = None
    for j in range(fill_idx, len(all_bars)):
        h, l = all_bars[j]['high'], all_bars[j]['low']
        if direction == "BUY":
            if l <= sl:
                outcome, exit_price = "SL", sl
            elif h >= tp:
                outcome, exit_price = "TP", tp
        else:
            if h >= sl:
                outcome, exit_price = "SL", sl
            elif l <= tp:
                outcome, exit_price = "TP", tp
        if outcome != "OPEN":
            exit_time = datetime.fromtimestamp(all_bars[j]['time'])
            break

    if outcome == "OPEN":
        continue

    last_trade_idx = i
    diff = (exit_price - entry) if direction == "BUY" else (entry - exit_price)
    usd = diff - SPREAD
    trades.append({
        'time': signal_time.strftime('%Y-%m-%d %H:%M'),
        'fill_time': datetime.fromtimestamp(all_bars[fill_idx]['time']).strftime('%Y-%m-%d %H:%M'),
        'exit_time': exit_time.strftime('%Y-%m-%d %H:%M') if exit_time else '-',
        'dir': direction,
        'entry': round(entry, 2),
        'sl': round(sl, 2),
        'tp': round(tp, 2),
        'outcome': outcome,
        'profit': round(usd, 2),
        'reason': sig.get('reason', ''),
    })

df = pd.DataFrame(trades)
out_csv = f"{args.out_prefix}_trades.csv"
df.to_csv(out_csv, index=False)

n = len(df)
print(f"Signals filled: {n} | Cancelled (no fill): {cancelled}")
if n > 0:
    wins = (df['outcome'] == 'TP').sum()
    losses = (df['outcome'] == 'SL').sum()
    net = df['profit'].sum()
    wr = wins / (wins + losses) * 100 if wins + losses else 0
    gw = df.loc[df['profit'] > 0, 'profit'].sum()
    gl = -df.loc[df['profit'] < 0, 'profit'].sum()
    pf = gw / gl if gl > 0 else float('inf')
    print(f"TP {wins} | SL {losses} | WinRate {wr:.1f}% | Net {net:.2f} USD | PF {pf:.2f}")

    df['time'] = pd.to_datetime(df['time'])
    monthly = df.groupby(df['time'].dt.strftime('%Y-%m'))['profit'].agg(['count', 'sum'])
    print(" | ".join(f"{m}: n={int(r['count'])} {r['sum']:+.0f}" for m, r in monthly.iterrows()))

    df['date'] = df['time'].dt.date
    daily = []
    for d, grp in df.groupby('date'):
        tp_n = (grp['outcome'] == 'TP').sum()
        sl_n = (grp['outcome'] == 'SL').sum()
        daily.append({'date': d, 'trades': len(grp), 'win': tp_n, 'loss': sl_n,
                      'net_profit': round(grp['profit'].sum(), 2),
                      'win_rate': round(tp_n / (tp_n + sl_n) * 100, 2) if tp_n + sl_n else 0})
    ddf = pd.DataFrame(daily)
    ddf.to_csv(f"{args.out_prefix}_daily.csv", index=False)
    neg_days = (ddf['net_profit'] < 0).sum()
    print(f"Days: {len(ddf)} | Negative days: {neg_days} | Avg/day {ddf['net_profit'].mean():.2f}")
