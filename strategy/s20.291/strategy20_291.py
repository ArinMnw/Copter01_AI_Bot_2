# -*- coding: utf-8 -*-
"""S20.291 — QQE (Quantitative Qualitative Estimation) Cross

แนวคิด: QQE: RSI14 ที่ smooth EMA5 เทียบ trailing line จาก ATR ของ RSI (Wilder 27 × 4.236) — RSI-smooth ตัด trailing line ขึ้นใต้ 50 → BUY; ตัดลงเหนือ 50 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.291', 'name': 'QQE (Quantitative Qualitative Estimation) Cross', 'concept': 'QQE: RSI14 ที่ smooth EMA5 เทียบ trailing line จาก ATR ของ RSI (Wilder 27 × 4.236) — RSI-smooth ตัด trailing line ขึ้นใต้ 50 → BUY; ตัดลงเหนือ 50 → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    rs = I.ema(I.rsi(df["close"], 14), 5).to_numpy()
    atr_r = I.ema(I.ema(pd.Series(np.abs(np.diff(rs, prepend=np.nan))), 27), 27).to_numpy() * 4.236
    n = len(rs); tl = np.full(n, np.nan)
    for i in range(1, n):
        if not (np.isfinite(rs[i]) and np.isfinite(atr_r[i])):
            continue
        p = tl[i - 1] if np.isfinite(tl[i - 1]) else rs[i]
        if rs[i] > p and rs[i - 1] > p:
            tl[i] = max(p, rs[i] - atr_r[i])
        elif rs[i] < p and rs[i - 1] < p:
            tl[i] = min(p, rs[i] + atr_r[i])
        else:
            tl[i] = rs[i] - atr_r[i] if rs[i] > p else rs[i] + atr_r[i]
    r, t = pd.Series(rs, index=df.index), pd.Series(tl, index=df.index)
    return I.sig_from(I.cross_up(r, t) & (r < 50), I.cross_dn(r, t) & (r > 50))
