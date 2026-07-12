"""Sweep S103 hyperparameters in-process (180 days, half-split report)."""
import sys
import os
from datetime import datetime

import MetaTrader5 as mt5
import pandas as pd

sys.path.append(os.path.abspath(r'd:\Project\Copter01_AI_Bot_2'))
import config
from sim_s30_backtest import fetch_bars
import strategy103

SYMBOL = "XAUUSD.iux"
TF = "M5"
DAYS = 180
SPREAD = 0.20
LOOKBACK = 150
FILL_BARS = 6
COOLDOWN = 10

if not config.mt5_initialize(mt5):
    print("MT5 init failed")
    sys.exit(1)
all_bars = fetch_bars(SYMBOL, TF, DAYS, extra_bars=300)
mt5.shutdown()
print(f"bars: {len(all_bars)}")


def run(cfg):
    cfg = dict(cfg)
    cooldown = cfg.pop("_cooldown", COOLDOWN)
    trades = []
    cancelled = 0
    last_trade_idx = -1000
    for i in range(LOOKBACK, len(all_bars) - 2):
        if i - last_trade_idx < cooldown:
            continue
        rates_slice = all_bars[i - LOOKBACK + 1: i + 1]
        dt_bkk = datetime.fromtimestamp(rates_slice[-1]['time'])
        sig = strategy103.detect_s103(rates_slice, tf=TF, dt_bkk=dt_bkk, cfg=cfg)
        if not sig or sig.get("signal") not in ("BUY", "SELL"):
            continue
        direction, entry, sl, tp = sig["signal"], sig["entry"], sig["sl"], sig["tp"]
        if sig.get("order_type") == "market":
            fill_idx = i + 1
            entry = float(all_bars[fill_idx]["open"])  # market = open แท่งถัดไปจริง
        else:
            fill_idx = None
            for j in range(i + 1, min(i + 1 + FILL_BARS, len(all_bars))):
                h, l = all_bars[j]['high'], all_bars[j]['low']
                if (direction == "BUY" and l <= entry - SPREAD) or (direction == "SELL" and h >= entry + SPREAD):
                    fill_idx = j
                    break
            if fill_idx is None:
                cancelled += 1
                last_trade_idx = i
                continue
        outcome = None
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
            if outcome:
                break
        if not outcome:
            continue
        last_trade_idx = i
        diff = (exit_price - entry) if direction == "BUY" else (entry - exit_price)
        trades.append({'profit': diff - SPREAD,
                       'time': datetime.fromtimestamp(all_bars[i]['time'])})
    if not trades:
        return {'n': 0, 'wr': 0, 'net': 0, 'pf': 0, 'cancelled': cancelled,
                'halves': '', 'monthly': ''}
    df = pd.DataFrame(trades)
    wins = (df['profit'] > 0).sum()
    losses = (df['profit'] < 0).sum()
    gw = df.loc[df['profit'] > 0, 'profit'].sum()
    gl = -df.loc[df['profit'] < 0, 'profit'].sum()
    monthly = df.groupby(df['time'].dt.strftime('%Y-%m'))['profit'].agg(['count', 'sum'])
    mid = df['time'].min() + (df['time'].max() - df['time'].min()) / 2
    halves = []
    for label, part in (("H1", df[df['time'] < mid]), ("H2", df[df['time'] >= mid])):
        if len(part) == 0:
            halves.append(f"{label}: n=0")
            continue
        w = (part['profit'] > 0).sum()
        l = (part['profit'] < 0).sum()
        halves.append(f"{label}: n={len(part)} wr={w/(w+l)*100:.0f}% net={part['profit'].sum():+.0f}")
    return {'n': len(df), 'wr': wins / (wins + losses) * 100 if wins + losses else 0,
            'net': df['profit'].sum(), 'pf': gw / gl if gl > 0 else float('inf'),
            'cancelled': cancelled, 'halves': " | ".join(halves),
            'monthly': " | ".join(f"{m}: n={int(r['count'])} {r['sum']:+.0f}"
                                  for m, r in monthly.iterrows())}


V = {"MODE": "vwap"}
variants = [
    ("box_best (ref)", {"RANGE_BARS": 30, "SL_BUF_ATR": 0.3}),
    ("vwap_sd2.0", dict(V)),
    ("vwap_sd1.5", dict(V, VWAP_SD_MULT=1.5)),
    ("vwap_sd2.5", dict(V, VWAP_SD_MULT=2.5)),
    ("vwap_sd2+sl1.5", dict(V, VWAP_SL_SD=1.5)),
    ("vwap_sd2+half", dict(V, VWAP_TP_AT="half")),
    ("vwap_sd2+rsi60", dict(V, RSI_SELL_MIN=60.0, RSI_BUY_MAX=40.0)),
    ("vwap_sd2+no_rsi", dict(V, RSI_SELL_MIN=0.0, RSI_BUY_MAX=100.0)),
    ("vwap_sd2+nt", dict(V, TIME_FILTER_ENABLED=False)),
]

print(f"{'variant':<14}{'n':>5}{'cancel':>7}{'wr%':>7}{'net':>9}{'pf':>7}")
for name, over in variants:
    r = run(dict(over))
    print(f"{name:<14}{r['n']:>5}{r['cancelled']:>7}{r['wr']:>7.1f}{r['net']:>9.2f}{r['pf']:>7.2f}")
    if r.get('halves'):
        print(f"    {r['halves']}")
    if r.get('monthly'):
        print(f"    {r['monthly']}")
