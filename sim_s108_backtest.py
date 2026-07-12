"""Backtest S108 Black Box — walk-forward RandomForest (no temporal leakage).

ห้ามใช้ ml_model.pkl ของระบบใน backtest (เทรนจากช่วงเวลาปัจจุบัน = แอบรู้อนาคต)
sim นี้เทรนโมเดลจาก "อดีตของ timeline เท่านั้น" แล้ว retrain เป็นช่วงๆ:
  - เก็บ sample: feature 9 ตัว (ฟอร์แมต ml_scoring) + label = TP มาก่อน SL (ATR-based)
  - sample จะเข้าคลังเทรนได้ก็ต่อเมื่อ "ผลของมันปิดจบไปแล้ว" ก่อนแท่งตัดสินใจปัจจุบัน
  - retrain ทุก RETRAIN แท่ง ด้วยคลังที่มี ณ เวลานั้น
กฎ Reality Check: SL-first, market fill ที่ open แท่งถัดไป, spread หักทุกไม้
"""
import sys
import os
import argparse
from datetime import datetime

import numpy as np
import pandas as pd
import MetaTrader5 as mt5
from sklearn.ensemble import RandomForestClassifier

sys.path.append(os.path.abspath(r'd:\Project\Copter01_AI_Bot_2'))
import config
from sim_s30_backtest import fetch_bars
import ml_scoring
import strategy108

parser = argparse.ArgumentParser(description="Backtest S108 Black Box (walk-forward RF)")
parser.add_argument("--days", type=int, default=180)
parser.add_argument("--tf", type=str, default="M5")
parser.add_argument("--cooldown", type=int, default=10)
parser.add_argument("--out-prefix", type=str, default="s108")
parser.add_argument("--threshold", type=float, default=0.55)
parser.add_argument("--min-edge", type=float, default=0.05)
parser.add_argument("--sl-atr", type=float, default=1.5)
parser.add_argument("--tp-rr", type=float, default=1.0)
parser.add_argument("--horizon", type=int, default=60, help="Bars to resolve sample label")
parser.add_argument("--sample-every", type=int, default=3)
parser.add_argument("--retrain", type=int, default=2000)
parser.add_argument("--min-train", type=int, default=8000)
args = parser.parse_args()

SYMBOL = "XAUUSD.iux"
TF = args.tf
SPREAD = 0.20
LOOKBACK = 120
FEAT_KEYS = strategy108.FEAT_V2_KEYS  # feature set v2 (stationary ทั้งหมด)

if not config.mt5_initialize(mt5):
    print("MT5 init failed")
    sys.exit(1)
all_bars = fetch_bars(SYMBOL, TF, args.days, extra_bars=300)
mt5.shutdown()
if all_bars is None or len(all_bars) == 0:
    print("Failed to fetch")
    sys.exit(1)
n_bars = len(all_bars)
print(f"bars: {n_bars}")


def atr_at(i, period=14):
    trs = []
    for k in range(i - period + 1, i + 1):
        h, l = all_bars[k]['high'], all_bars[k]['low']
        pc = all_bars[k - 1]['close']
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / period


def resolve_label(i, direction, atr):
    """ผล TP-first(1)/SL-first(0)/None ของ sample ที่แท่ง i (entry = open i+1)
    คืน (label, resolve_idx)"""
    if i + 1 >= n_bars:
        return None, None
    entry = float(all_bars[i + 1]['open'])
    sl_dist = atr * args.sl_atr
    if direction == "BUY":
        sl, tp = entry - sl_dist, entry + sl_dist * args.tp_rr
    else:
        sl, tp = entry + sl_dist, entry - sl_dist * args.tp_rr
    for j in range(i + 1, min(i + 1 + args.horizon, n_bars)):
        h, l = all_bars[j]['high'], all_bars[j]['low']
        if direction == "BUY":
            if l <= sl:
                return 0, j
            if h >= tp:
                return 1, j
        else:
            if h >= sl:
                return 0, j
            if l <= tp:
                return 1, j
    return None, None


# --- Phase A: สร้าง samples (label ใช้อนาคตของ sample เอง แต่จะถูกใช้เทรน
#     ก็ต่อเมื่อ resolve_idx < แท่งตัดสินใจ — บังคับใน Phase B) ---
samples = []  # (bar_idx, resolve_idx, feature_vector, label)
for i in range(LOOKBACK, n_bars - 2, args.sample_every):
    rates_slice = all_bars[i - LOOKBACK + 1: i + 1]
    dt = datetime.fromtimestamp(all_bars[i]['time'])
    base = strategy108.extract_features_v2(rates_slice, dt.hour)
    if base is None:
        continue
    atr = atr_at(i)
    if atr <= 0:
        continue
    for direction, fb, fs in (("BUY", 1, 0), ("SELL", 0, 1)):
        label, ridx = resolve_label(i, direction, atr)
        if label is None:
            continue
        f = dict(base, is_buy=fb, is_sell=fs)
        samples.append((i, ridx, [f[k] for k in FEAT_KEYS], label))
samples.sort(key=lambda s: s[0])
print(f"samples: {len(samples)}")

# --- Phase B: walk-forward decide + trade ---
cfg = {"ML_THRESHOLD": args.threshold, "MIN_EDGE": args.min_edge,
       "SL_ATR_MULT": args.sl_atr, "TP_RR": args.tp_rr}

model = None
last_train_i = -10**9
sample_ptr = 0
train_X, train_y = [], []
trades = []
last_trade_idx = -1000

for i in range(LOOKBACK, n_bars - 2):
    # เพิ่ม sample ที่ "ปิดจบแล้ว" เข้าคลัง (resolve_idx < i)
    while sample_ptr < len(samples) and samples[sample_ptr][0] < i:
        s_i, ridx, vec, label = samples[sample_ptr]
        if ridx < i:
            train_X.append(vec)
            train_y.append(label)
            sample_ptr += 1
        else:
            break  # sample เก่าสุดยังไม่ปิดจบ — รอ (list sort ตาม bar_idx)

    if i - last_train_i >= args.retrain and len(train_X) >= args.min_train:
        model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        model.fit(train_X, train_y)
        last_train_i = i

    if model is None or i - last_trade_idx < args.cooldown:
        continue

    rates_slice = all_bars[i - LOOKBACK + 1: i + 1]
    dt_bkk = datetime.fromtimestamp(all_bars[i]['time'])

    def scorer(f):
        return float(model.predict_proba([[f[k] for k in FEAT_KEYS]])[0][1])

    sig = strategy108.detect_s108(rates_slice, tf=TF, dt_bkk=dt_bkk, cfg=cfg, scorer=scorer)
    if not sig or sig.get("signal") not in ("BUY", "SELL"):
        continue

    direction = sig["signal"]
    fill_idx = i + 1
    entry = float(all_bars[fill_idx]['open'])  # market = open แท่งถัดไปจริง
    sl_dist = abs(sig["entry"] - sig["sl"])
    if direction == "BUY":
        sl, tp = entry - sl_dist, entry + sl_dist * args.tp_rr
    else:
        sl, tp = entry + sl_dist, entry - sl_dist * args.tp_rr

    outcome, exit_price, exit_idx = None, None, None
    for j in range(fill_idx, n_bars):
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
            exit_idx = j
            break
    if not outcome:
        continue

    last_trade_idx = i
    diff = (exit_price - entry) if direction == "BUY" else (entry - exit_price)
    trades.append({
        'time': datetime.fromtimestamp(all_bars[i]['time']).strftime('%Y-%m-%d %H:%M'),
        'exit_time': datetime.fromtimestamp(all_bars[exit_idx]['time']).strftime('%Y-%m-%d %H:%M'),
        'dir': direction,
        'entry': round(entry, 2),
        'sl': round(sl, 2),
        'tp': round(tp, 2),
        'outcome': outcome,
        'profit': round(diff - SPREAD, 2),
        'ml_prob': round(sig.get('ml_prob', 0), 3),
    })

df = pd.DataFrame(trades)
df.to_csv(f"{args.out_prefix}_trades.csv", index=False)

n = len(df)
print(f"Trades: {n} | train pool (final): {len(train_X)}")
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
    mid = df['time'].min() + (df['time'].max() - df['time'].min()) / 2
    for label, part in (("H1", df[df['time'] < mid]), ("H2", df[df['time'] >= mid])):
        if len(part):
            w = (part['outcome'] == 'TP').sum()
            l = (part['outcome'] == 'SL').sum()
            print(f"{label}: n={len(part)} wr={w/(w+l)*100:.0f}% net={part['profit'].sum():+.0f}")
