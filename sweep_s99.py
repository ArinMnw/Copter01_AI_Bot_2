"""Sweep S99 hyperparameters in-process (fetch bars once)."""
import sys
import os
import itertools
from datetime import datetime

import MetaTrader5 as mt5
import pandas as pd

sys.path.append(os.path.abspath(r'd:\Project\Copter01_AI_Bot_2'))
import config
from sim_s30_backtest import fetch_bars
import strategy99

SYMBOL = "XAUUSD.iux"
TF = "M5"
DAYS = 180
SPREAD = 0.20
LOOKBACK = 150
FILL_BARS = 12
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
        sig = strategy99.detect_s99(rates_slice, tf=TF, dt_bkk=dt_bkk, cfg=cfg)
        if not sig or sig.get("signal") not in ("BUY", "SELL"):
            continue
        direction, entry, sl, tp = sig["signal"], sig["entry"], sig["sl"], sig["tp"]
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
        trades.append({'outcome': outcome, 'profit': diff - SPREAD,
                       'time': datetime.fromtimestamp(all_bars[i]['time'])})
    if not trades:
        return {'n': 0, 'wr': 0, 'net': 0, 'pf': 0, 'cancelled': cancelled, 'neg_days': 0, 'days': 0, 'monthly': ''}
    df = pd.DataFrame(trades)
    monthly = df.groupby(df['time'].dt.strftime('%Y-%m'))['profit'].agg(['count', 'sum'])
    monthly_str = " | ".join(f"{m}: n={int(r['count'])} {r['sum']:+.0f}" for m, r in monthly.iterrows())
    wins = (df['outcome'] == 'TP').sum()
    losses = (df['outcome'] == 'SL').sum()
    net = df['profit'].sum()
    gw = df.loc[df['profit'] > 0, 'profit'].sum()
    gl = -df.loc[df['profit'] < 0, 'profit'].sum()
    daily = df.groupby(df['time'].dt.date)['profit'].sum()
    return {'n': len(df), 'wr': wins / (wins + losses) * 100 if wins + losses else 0,
            'net': net, 'pf': gw / gl if gl > 0 else float('inf'),
            'cancelled': cancelled, 'neg_days': (daily < 0).sum(), 'days': len(daily),
            'monthly': monthly_str}


base = {}
variants = [
    # widen FVG branch for more trades + nearby plateau
    ("d10+fvg", {"DISP_BODY_ATR": 1.0, "REQUIRE_FVG": True}),
    ("d12+fvg", {"DISP_BODY_ATR": 1.2, "REQUIRE_FVG": True}),
    ("d14+fvg", {"DISP_BODY_ATR": 1.4, "REQUIRE_FVG": True}),
    ("d12+fvg+r62", {"DISP_BODY_ATR": 1.2, "REQUIRE_FVG": True, "ENTRY_RETRACE": 0.62}),
    ("d12+fvg+r40", {"DISP_BODY_ATR": 1.2, "REQUIRE_FVG": True, "ENTRY_RETRACE": 0.40}),
    ("d10+fvg+age40", {"DISP_BODY_ATR": 1.0, "REQUIRE_FVG": True, "SWEEP_MAX_AGE": 40}),
    ("d12+fvg+nt", {"DISP_BODY_ATR": 1.2, "REQUIRE_FVG": True, "TIME_FILTER_ENABLED": False}),
    ("d12+fvg+cd0", {"DISP_BODY_ATR": 1.2, "REQUIRE_FVG": True, "_cooldown": 0}),
]

print(f"{'variant':<14}{'n':>5}{'cancel':>7}{'wr%':>7}{'net':>9}{'pf':>7}{'negd':>6}{'days':>6}")
for name, over in variants:
    cfg = dict(base)
    cfg.update(over)
    r = run(cfg)
    print(f"{name:<14}{r['n']:>5}{r['cancelled']:>7}{r['wr']:>7.1f}{r['net']:>9.2f}{r['pf']:>7.2f}{r['neg_days']:>6}{r['days']:>6}")
    if r.get('monthly'):
        print(f"    {r['monthly']}")
