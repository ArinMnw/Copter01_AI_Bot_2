"""Sweep S100 hyperparameters in-process (fetch bars once, 90 days)."""
import sys
import os
from datetime import datetime

import MetaTrader5 as mt5
import pandas as pd

sys.path.append(os.path.abspath(r'd:\Project\Copter01_AI_Bot_2'))
import config
from sim_s30_backtest import fetch_bars
import strategy107

SYMBOL = "XAUUSD.iux"
TF = "M5"
DAYS = 180
SPREAD = 0.20
LOOKBACK = 160
FILL_BARS = 144
COOLDOWN = 10

if not config.mt5_initialize(mt5):
    print("MT5 init failed")
    sys.exit(1)
all_bars = fetch_bars(SYMBOL, TF, DAYS, extra_bars=800)
mt5.shutdown()
print(f"bars: {len(all_bars)}")


def run(cfg):
    cfg = dict(cfg)
    cooldown = cfg.pop("_cooldown", COOLDOWN)
    fill_bars = cfg.pop("_fill_bars", FILL_BARS)
    trades = []
    cancelled = 0
    last_trade_idx = -1000
    for i in range(LOOKBACK, len(all_bars) - 2):
        if i - last_trade_idx < cooldown:
            continue
        rates_slice = all_bars[i - LOOKBACK + 1: i + 1]
        dt_bkk = datetime.fromtimestamp(rates_slice[-1]['time'])
        sig = strategy107.detect_s107(rates_slice, tf=TF, dt_bkk=dt_bkk, cfg=cfg)
        if not sig or sig.get("signal") not in ("BUY", "SELL"):
            continue
        direction, entry, sl, tp = sig["signal"], sig["entry"], sig["sl"], sig["tp"]
        fill_idx = None
        for j in range(i + 1, min(i + 1 + fill_bars, len(all_bars))):
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
        trades.append({'outcome': outcome, 'profit': diff - SPREAD,
                       'time': datetime.fromtimestamp(all_bars[i]['time'])})
    if not trades:
        return {'n': 0, 'wr': 0, 'net': 0, 'pf': 0, 'cancelled': cancelled, 'monthly': ''}
    df = pd.DataFrame(trades)
    wins = (df['outcome'] == 'TP').sum()
    losses = (df['outcome'] == 'SL').sum()
    gw = df.loc[df['profit'] > 0, 'profit'].sum()
    gl = -df.loc[df['profit'] < 0, 'profit'].sum()
    monthly = df.groupby(df['time'].dt.strftime('%Y-%m'))['profit'].agg(['count', 'sum'])
    mid = df['time'].min() + (df['time'].max() - df['time'].min()) / 2
    halves = []
    for label, part in (("H1", df[df['time'] < mid]), ("H2", df[df['time'] >= mid])):
        if len(part) == 0:
            halves.append(f"{label}: n=0")
            continue
        w = (part['outcome'] == 'TP').sum()
        l = (part['outcome'] == 'SL').sum()
        halves.append(f"{label}: n={len(part)} wr={w/(w+l)*100:.0f}% net={part['profit'].sum():+.0f}")
    return {'n': len(df), 'wr': wins / (wins + losses) * 100 if wins + losses else 0,
            'net': df['profit'].sum(), 'pf': gw / gl if gl > 0 else float('inf'),
            'cancelled': cancelled, 'halves': " | ".join(halves),
            'monthly': " | ".join(f"{m}: n={int(r['count'])} {r['sum']:+.0f}"
                                  for m, r in monthly.iterrows())}


variants = [
    ("d18+rr1.5", {"BOS_DISP_ATR": 1.8, "TP_RR": 1.5}),
    ("d18+cd60", {"BOS_DISP_ATR": 1.8, "_cooldown": 60}),
    ("d18+rr1.5+cd60", {"BOS_DISP_ATR": 1.8, "TP_RR": 1.5, "_cooldown": 60}),
    ("d15+rr1.5+cd60", {"BOS_DISP_ATR": 1.5, "TP_RR": 1.5, "_cooldown": 60}),
    ("d18+depth0.5", {"BOS_DISP_ATR": 1.8, "OB_ENTRY_DEPTH": 0.5}),
    ("d18+rr1.5+ob1.5", {"BOS_DISP_ATR": 1.8, "TP_RR": 1.5, "OB_MAX_SIZE_ATR": 1.5}),
    ("d22+rr1.5", {"BOS_DISP_ATR": 2.2, "TP_RR": 1.5}),
    ("d18+rr1.2", {"BOS_DISP_ATR": 1.8, "TP_RR": 1.2}),
]

print(f"{'variant':<18}{'n':>5}{'cancel':>7}{'wr%':>7}{'net':>9}{'pf':>7}")
for name, over in variants:
    r = run(dict(over))
    print(f"{name:<18}{r['n']:>5}{r['cancelled']:>7}{r['wr']:>7.1f}{r['net']:>9.2f}{r['pf']:>7.2f}")
    if r.get('halves'):
        print(f"    {r['halves']}")
    if r.get('monthly'):
        print(f"    {r['monthly']}")
