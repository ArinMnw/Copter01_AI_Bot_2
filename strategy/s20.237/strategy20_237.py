# -*- coding: utf-8 -*-
"""S20.237 — Ehlers FRAMA Cross

แนวคิด: Fractal Adaptive MA (Ehlers, 16): alpha ปรับตาม fractal dimension; ราคาปิดตัด FRAMA ขึ้นพร้อม FRAMA ชันขึ้น → BUY; ตัดลง + FRAMA ลง → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.237', 'name': 'Ehlers FRAMA Cross', 'concept': 'Fractal Adaptive MA (Ehlers, 16): alpha ปรับตาม fractal dimension; ราคาปิดตัด FRAMA ขึ้นพร้อม FRAMA ชันขึ้น → BUY; ตัดลง + FRAMA ลง → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    N = 16
    h, l, c = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    n = len(c); fr = np.full(n, np.nan)
    for i in range(N, n):
        h1, l1 = h[i - N + 1:i - N // 2 + 1].max(), l[i - N + 1:i - N // 2 + 1].min()
        h2, l2 = h[i - N // 2 + 1:i + 1].max(), l[i - N // 2 + 1:i + 1].min()
        h3, l3 = h[i - N + 1:i + 1].max(), l[i - N + 1:i + 1].min()
        n1, n2, n3 = (h1 - l1) / (N / 2), (h2 - l2) / (N / 2), (h3 - l3) / N
        dim = (np.log(n1 + n2) - np.log(n3)) / np.log(2) if n1 > 0 and n2 > 0 and n3 > 0 else 1.0
        al = float(np.clip(np.exp(-4.6 * (dim - 1)), 0.01, 1.0))
        fr[i] = c[i] if not np.isfinite(fr[i - 1]) else al * c[i] + (1 - al) * fr[i - 1]
    f = pd.Series(fr, index=df.index); cs = df["close"]
    return I.sig_from(I.cross_up(cs, f) & (f > f.shift(3)), I.cross_dn(cs, f) & (f < f.shift(3)))
