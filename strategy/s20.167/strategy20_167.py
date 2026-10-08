# -*- coding: utf-8 -*-
"""S20.167 — Ehlers Laguerre RSI Extremes

แนวคิด: Ehlers Laguerre RSI (gamma 0.6): ตัดขึ้นเหนือ 0.15 จาก oversold → BUY, ตัดลงใต้ 0.85 → SELL; กรองด้วย SMA100 (เทรดตาม bias ใหญ่เท่านั้น)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.167', 'name': 'Ehlers Laguerre RSI Extremes', 'concept': 'Ehlers Laguerre RSI (gamma 0.6): ตัดขึ้นเหนือ 0.15 จาก oversold → BUY, ตัดลงใต้ 0.85 → SELL; กรองด้วย SMA100 (เทรดตาม bias ใหญ่เท่านั้น)', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 20}


def generate(df, tf):
    c = df["close"].to_numpy(); g = 0.6
    n = len(c); L0 = L1 = L2 = L3 = c[0]
    lr = np.full(n, np.nan)
    for i in range(n):
        p0, p1, p2 = L0, L1, L2
        L0 = (1 - g) * c[i] + g * L0
        L1 = -g * L0 + p0 + g * L1
        L2 = -g * L1 + p1 + g * L2
        L3 = -g * L2 + p2 + g * L3
        cu = max(L0 - L1, 0) + max(L1 - L2, 0) + max(L2 - L3, 0)
        cd = max(L1 - L0, 0) + max(L2 - L1, 0) + max(L3 - L2, 0)
        lr[i] = cu / (cu + cd) if cu + cd > 0 else 0.5
    s = pd.Series(lr, index=df.index)
    s100 = I.sma(df["close"], 100)
    return I.sig_from(I.cross_up(s, 0.15) & (df["close"] > s100), I.cross_dn(s, 0.85) & (df["close"] < s100))
