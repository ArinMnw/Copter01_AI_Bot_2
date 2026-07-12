import sys
import os
import pandas as pd
import MetaTrader5 as mt5
import argparse
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(r'd:\Project\Copter01_AI_Bot_2'))
import config
from sim_s30_backtest import fetch_bars
import strategy106

parser = argparse.ArgumentParser(description="Backtest S106 Judas Swing Killzone Fakeout")
parser.add_argument("--days", type=int, default=90)
parser.add_argument("--start", type=str, help="YYYY-MM-DD")
parser.add_argument("--end", type=str, help="YYYY-MM-DD")
parser.add_argument("--fill-bars", type=int, default=6, help="For limit entry mode")
parser.add_argument("--cooldown", type=int, default=10)
parser.add_argument("--tf", type=str, default="M5")
parser.add_argument("--out-prefix", type=str, default="s106")
# hyperparameter overrides
parser.add_argument("--regime-pctl", type=float, default=None)
parser.add_argument("--range-bars", type=int, default=None)
parser.add_argument("--rsi-sell-min", type=float, default=None)
parser.add_argument("--rsi-buy-max", type=float, default=None)
parser.add_argument("--zscore-min", type=float, default=None)
parser.add_argument("--no-zscore", action="store_true")
parser.add_argument("--sl-buf", type=float, default=None)
parser.add_argument("--tp-opposite", action="store_true")
parser.add_argument("--entry-edge", action="store_true")
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

cfg = {}
if args.regime_pctl is not None:
    cfg["ATR_REGIME_PCTL_MAX"] = args.regime_pctl
if args.range_bars is not None:
    cfg["RANGE_BARS"] = args.range_bars
if args.rsi_sell_min is not None:
    cfg["RSI_SELL_MIN"] = args.rsi_sell_min
if args.rsi_buy_max is not None:
    cfg["RSI_BUY_MAX"] = args.rsi_buy_max
if args.zscore_min is not None:
    cfg["ZSCORE_MIN"] = args.zscore_min
if args.no_zscore:
    cfg["ZSCORE_ENABLED"] = False
if args.sl_buf is not None:
    cfg["SL_BUF_ATR"] = args.sl_buf
if args.tp_opposite:
    cfg["TP_TARGET"] = "opposite"
if args.entry_edge:
    cfg["ENTRY_AT"] = "edge"
if args.no_time_filter:
    cfg["TIME_FILTER_ENABLED"] = False

trades = []
cancelled = 0
last_trade_idx = -1000

for i in range(LOOKBACK, len(all_bars) - 2):
    if i - last_trade_idx < args.cooldown:
        continue

    rates_slice = all_bars[i - LOOKBACK + 1: i + 1]
    dt_bkk = datetime.fromtimestamp(rates_slice[-1]['time'])
    sig = strategy106.detect_s106(rates_slice, tf=TF, dt_bkk=dt_bkk, cfg=cfg)

    if not sig or sig.get("signal") not in ("BUY", "SELL"):
        continue

    direction = sig["signal"]
    entry, sl, tp = sig["entry"], sig["sl"], sig["tp"]
    signal_time = datetime.fromtimestamp(all_bars[i]['time'])

    # --- fill ---
    if sig.get("order_type") == "market":
        fill_idx = i + 1
        entry = float(all_bars[fill_idx]["open"])  # market เข้าที่ open แท่งถัดไปจริง (กัน gap bias)
    else:
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

    # --- simulate (conservative: SL first) ---
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
df.to_csv(f"{args.out_prefix}_trades.csv", index=False)

n = len(df)
print(f"Trades: {n} | Cancelled (no fill): {cancelled}")
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
    daily = df.groupby('date')['profit'].agg(['count', 'sum']).reset_index()
    daily.columns = ['date', 'trades', 'net_profit']
    daily.to_csv(f"{args.out_prefix}_daily.csv", index=False)
    print(f"Days: {len(daily)} | Negative days: {(daily['net_profit'] < 0).sum()} | Avg/day {daily['net_profit'].mean():.2f}")
