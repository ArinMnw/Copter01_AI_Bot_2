"""Sweep S112 SMC Liquidity Sniper in-process (fetch M1 once). 60 วัน."""
import sys
import os
from datetime import datetime

import MetaTrader5 as mt5
import pandas as pd

sys.path.append(os.path.abspath(r'd:\Project\Copter01_AI_Bot_2'))
import config
from sim_s30_backtest import fetch_bars
import strategy112

SYMBOL = "XAUUSD.iux"
TF = "M1"
DAYS = 60
SPREAD = 0.20
LOOKBACK = 750
FILL_BARS = 5

if not config.mt5_initialize(mt5):
    print("MT5 init failed")
    sys.exit(1)
all_bars = fetch_bars(SYMBOL, TF, DAYS, extra_bars=800)
mt5.shutdown()
print(f"bars: {len(all_bars)}")
N = len(all_bars)


def run(cfg):
    cfg = dict(cfg)
    cooldown = cfg.pop("_cooldown", 15)
    trades = []
    cancelled = 0
    last_i = -10000
    for i in range(LOOKBACK, N - 2):
        if i - last_i < cooldown:
            continue
        sl_ = all_bars[i - LOOKBACK + 1: i + 1]
        dt_bkk = datetime.fromtimestamp(sl_[-1]['time'])
        sig = strategy112.detect_s112(sl_, tf=TF, dt_bkk=dt_bkk, cfg=cfg)
        if not sig or sig.get("signal") not in ("BUY", "SELL"):
            continue
        direction, entry, sl, tp = sig["signal"], sig["entry"], sig["sl"], sig["tp"]
        fill_idx = None
        for j in range(i + 1, min(i + 1 + FILL_BARS, N)):
            h, l = all_bars[j]['high'], all_bars[j]['low']
            if (direction == "BUY" and l <= entry - SPREAD) or (direction == "SELL" and h >= entry + SPREAD):
                fill_idx = j
                break
        if fill_idx is None:
            cancelled += 1
            last_i = i
            continue
        outcome = None
        for j in range(fill_idx, N):
            h, l = all_bars[j]['high'], all_bars[j]['low']
            if direction == "BUY":
                if l <= sl:
                    outcome, px = "SL", sl
                elif h >= tp:
                    outcome, px = "TP", tp
            else:
                if h >= sl:
                    outcome, px = "SL", sl
                elif l <= tp:
                    outcome, px = "TP", tp
            if outcome:
                break
        if not outcome:
            continue
        last_i = i
        diff = (px - entry) if direction == "BUY" else (entry - px)
        trades.append({'outcome': outcome, 'profit': diff - SPREAD,
                       'time': datetime.fromtimestamp(all_bars[i]['time'])})
    if not trades:
        return {'n': 0, 'wr': 0, 'net': 0, 'pf': 0, 'cancelled': cancelled, 'halves': ''}
    df = pd.DataFrame(trades)
    wins = (df['outcome'] == 'TP').sum()
    losses = (df['outcome'] == 'SL').sum()
    gw = df.loc[df['profit'] > 0, 'profit'].sum()
    gl = -df.loc[df['profit'] < 0, 'profit'].sum()
    mid = df['time'].min() + (df['time'].max() - df['time'].min()) / 2
    halves = []
    for lbl, part in (("H1", df[df['time'] < mid]), ("H2", df[df['time'] >= mid])):
        if len(part):
            w = (part['outcome'] == 'TP').sum()
            l = (part['outcome'] == 'SL').sum()
            halves.append(f"{lbl}: n={len(part)} wr={w/(w+l)*100:.0f}% net={part['profit'].sum():+.0f}")
    return {'n': len(df), 'wr': wins / (wins + losses) * 100 if wins + losses else 0,
            'net': df['profit'].sum(), 'pf': gw / gl if gl > 0 else float('inf'),
            'cancelled': cancelled, 'halves': " | ".join(halves)}


L = {"TRADE_HOURS": (14, 15, 16, 17)}
variants = [
    ("london (ref)", dict(L)),
    ("london+rr2", dict(L, TP_RR=2.0)),
    ("london+leg5", dict(L, MIN_LEG_PTS=5.0)),
    ("london+leg5+rr2", dict(L, MIN_LEG_PTS=5.0, TP_RR=2.0)),
    ("london+leg3+rr2", dict(L, MIN_LEG_PTS=3.0, TP_RR=2.0)),
    ("london+sw20", dict(L, SWEEP_WINDOW=20)),
    ("london+noreject", dict(L, REJECT_REQUIRED=False)),
    ("london13-17", {"TRADE_HOURS": (13,14,15,16,17)}),
    ("london+leg5+cd30", dict(L, MIN_LEG_PTS=5.0, _cooldown=30)),
]

print(f"{'variant':<14}{'n':>5}{'cancel':>7}{'wr%':>7}{'net':>9}{'pf':>7}")
for name, over in variants:
    r = run(dict(over))
    print(f"{name:<14}{r['n']:>5}{r['cancelled']:>7}{r['wr']:>7.1f}{r['net']:>9.2f}{r['pf']:>7.2f}")
    if r.get('halves'):
        print(f"    {r['halves']}")
