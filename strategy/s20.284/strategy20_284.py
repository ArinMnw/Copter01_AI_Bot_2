# -*- coding: utf-8 -*-
"""S20.284 — Chande VIDYA Breakout of Band

แนวคิด: VIDYA (Chande, CMO9-adaptive EMA14): ราคาปิดเหนือ VIDYA + 1 ATR (ออกจากโซน) ครั้งแรก → BUY; ต่ำกว่า VIDYA − 1 ATR → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.284', 'name': 'Chande VIDYA Breakout of Band', 'concept': 'VIDYA (Chande, CMO9-adaptive EMA14): ราคาปิดเหนือ VIDYA + 1 ATR (ออกจากโซน) ครั้งแรก → BUY; ต่ำกว่า VIDYA − 1 ATR → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    c = df["close"].to_numpy(); n = len(c)
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).rolling(9).sum().to_numpy(); dn = pd.Series(np.clip(-d, 0, None)).rolling(9).sum().to_numpy()
    cmo = np.abs((up - dn) / np.where(up + dn == 0, np.nan, up + dn))
    al = 2 / 15
    v = np.full(n, np.nan)
    for i in range(1, n):
        k = al * (cmo[i] if np.isfinite(cmo[i]) else 0)
        v[i] = c[i] if not np.isfinite(v[i - 1]) else k * c[i] + (1 - k) * v[i - 1]
    vs = pd.Series(v, index=df.index); a = I.atr(df, 14); cs = df["close"]
    ub, lb = vs + a, vs - a
    return I.sig_from((cs > ub) & (cs.shift(1) <= ub.shift(1)), (cs < lb) & (cs.shift(1) >= lb.shift(1)))
