# -*- coding: utf-8 -*-
"""S20.187 — Flat Linear-Regression Channel 2σ Re-entry

แนวคิด: Linear regression channel 100 แท่ง: เมื่อ slope แบน (<0.02 ATR/แท่ง) ราคาหลุดนอก ±2σ แล้วปิดกลับเข้าช่อง → fade กลับหาเส้นกลาง
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.187', 'name': 'Flat Linear-Regression Channel 2σ Re-entry', 'concept': 'Linear regression channel 100 แท่ง: เมื่อ slope แบน (<0.02 ATR/แท่ง) ราคาหลุดนอก ±2σ แล้วปิดกลับเข้าช่อง → fade กลับหาเส้นกลาง', 'sl_atr': 1.2, 'rr': 1.5, 'max_hold': 24}


def generate(df, tf):
    n = 100
    c = df["close"]
    x = np.arange(n, dtype=float)
    def fit(y):
        b, a0 = np.polyfit(x, y, 1)
        res = y - (a0 + b * x)
        return a0 + b * (n - 1), b, res.std()
    arr = c.to_numpy(); m = len(arr)
    mid = np.full(m, np.nan); slp = np.full(m, np.nan); sd = np.full(m, np.nan)
    for i in range(n - 1, m):
        mid[i], slp[i], sd[i] = fit(arr[i - n + 1:i + 1])
    mid, slp, sd = (pd.Series(v, index=df.index) for v in (mid, slp, sd))
    a = I.atr(df, 14)
    flat = slp.abs() < 0.02 * a
    lo, hi = mid - 2 * sd, mid + 2 * sd
    buy = flat & (c.shift(1) < lo.shift(1)) & (c > lo)
    sell = flat & (c.shift(1) > hi.shift(1)) & (c < hi)
    return I.sig_from(buy, sell)
