# -*- coding: utf-8 -*-
"""Conservative single-position backtest for S113 on MT5 closed bars."""

import argparse
from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5
import pandas as pd

import config
from sim_s30_backtest import fetch_bars
import strategy113


parser = argparse.ArgumentParser(description="Backtest S113 Wyckoff VSA Fractal Reversal")
parser.add_argument("--days", type=int, default=90)
parser.add_argument("--tf", choices=("M1", "M5", "M15"), default="M5")
parser.add_argument("--spread", type=float, default=0.20)
parser.add_argument("--out-prefix", default="s113")
parser.add_argument("--no-time-filter", action="store_true")
parser.add_argument("--volume-mult", type=float)
parser.add_argument("--squeeze-max", type=float)
parser.add_argument("--tp-rr", type=float)
parser.add_argument("--hours", help="Comma-separated BKK hours, e.g. 14,20")
args = parser.parse_args()

symbol = "XAUUSD.iux"
lookback = 220
BKK = timezone(timedelta(hours=7))
if not config.mt5_initialize(mt5):
    raise SystemExit("MT5 init failed")
bars = fetch_bars(symbol, args.tf, args.days, extra_bars=lookback + 50)
mt5.shutdown()
if bars is None or len(bars) <= lookback:
    raise SystemExit("Failed to fetch enough bars")
print(
    f"Bars={len(bars)} | "
    f"{datetime.fromtimestamp(int(bars[0]['time']), tz=BKK):%Y-%m-%d %H:%M} -> "
    f"{datetime.fromtimestamp(int(bars[-1]['time']), tz=BKK):%Y-%m-%d %H:%M} BKK"
)

cfg = {}
if args.no_time_filter:
    cfg["TIME_FILTER_ENABLED"] = False
if args.volume_mult is not None:
    cfg["VOLUME_SPIKE_MULT"] = args.volume_mult
if args.squeeze_max is not None:
    cfg["SQUEEZE_RATIO_MAX"] = args.squeeze_max
if args.tp_rr is not None:
    cfg["TP_RR"] = args.tp_rr
    cfg["TP_MAX_RR"] = args.tp_rr
if args.hours:
    cfg["TRADE_HOURS"] = tuple(int(value) for value in args.hours.split(","))

trades = []
next_free = lookback
signals = 0
for i in range(lookback, len(bars) - 1):
    if i < next_free:
        continue
    window = bars[i - lookback + 1:i + 1]
    dt_bkk = datetime.fromtimestamp(int(window[-1]["time"]), tz=BKK)
    signal = strategy113.detect_s113(window, args.tf, dt_bkk, cfg)
    expected_keys = (
        {"signal", "reason"} if signal.get("signal") == "WAIT"
        else {"signal", "entry", "sl", "tp", "reason"}
    )
    if set(signal) != expected_keys:
        raise AssertionError(f"S113 return contract mismatch: {set(signal)}")
    if signal["signal"] not in ("BUY", "SELL"):
        continue
    quoted_entry = float(signal["entry"])
    quoted_risk = (
        quoted_entry - float(signal["sl"])
        if signal["signal"] == "BUY"
        else float(signal["sl"]) - quoted_entry
    )
    quoted_reward = (
        float(signal["tp"]) - quoted_entry
        if signal["signal"] == "BUY"
        else quoted_entry - float(signal["tp"])
    )
    if quoted_risk <= 0 or quoted_reward / quoted_risk < 1.5 - 1e-9:
        raise AssertionError("S113 returned invalid risk or RR below 1:1.5")
    signals += 1
    direction = signal["signal"]
    fill_idx = i + 1
    entry = float(bars[fill_idx]["open"])
    sl, tp = float(signal["sl"]), float(signal["tp"])
    risk = entry - sl if direction == "BUY" else sl - entry
    if risk <= 0:
        continue

    outcome = None
    exit_idx = None
    exit_price = None
    for j in range(fill_idx, len(bars)):
        high, low = float(bars[j]["high"]), float(bars[j]["low"])
        if direction == "BUY":
            if low <= sl:
                outcome, exit_price = "SL", sl
            elif high >= tp:
                outcome, exit_price = "TP", tp
        else:
            if high >= sl:
                outcome, exit_price = "SL", sl
            elif low <= tp:
                outcome, exit_price = "TP", tp
        if outcome:
            exit_idx = j
            break
    if not outcome:
        break

    pnl = (exit_price - entry) if direction == "BUY" else (entry - exit_price)
    pnl -= float(args.spread)
    trades.append({
        "time": datetime.fromtimestamp(int(bars[i]["time"]), tz=BKK),
        "exit_time": datetime.fromtimestamp(int(bars[exit_idx]["time"]), tz=BKK),
        "direction": direction,
        "entry": round(entry, 2), "sl": sl, "tp": tp,
        "outcome": outcome, "profit": round(pnl, 2),
        "reason": signal["reason"],
    })
    next_free = exit_idx + 1

df = pd.DataFrame(trades)
df.to_csv(f"{args.out_prefix}_trades.csv", index=False)
print(f"TF {args.tf} | signals={signals} | closed={len(df)}")
if len(df):
    wins = int((df["profit"] > 0).sum())
    gross_win = float(df.loc[df["profit"] > 0, "profit"].sum())
    gross_loss = abs(float(df.loc[df["profit"] <= 0, "profit"].sum()))
    net = float(df["profit"].sum())
    equity = df["profit"].cumsum()
    drawdown = float((equity.cummax() - equity).max())
    print(
        f"WinRate={wins / len(df) * 100:.1f}% | Net={net:.2f} | "
        f"PF={gross_win / gross_loss if gross_loss else float('inf'):.2f} | "
        f"MaxDD={drawdown:.2f}"
    )
