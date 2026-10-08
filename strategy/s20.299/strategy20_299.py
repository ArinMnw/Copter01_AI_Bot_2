# -*- coding: utf-8 -*-
"""S20.299 — Ehlers Even Better Sinewave

แนวคิด: Ehlers Even Better Sinewave (high-pass 40 + super smoother 10, normalized): wave ตัดขึ้นเหนือ −0.8 จากก้น → BUY (cycle low); ตัดลงใต้ +0.8 → SELL (cycle high)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.299', 'name': 'Ehlers Even Better Sinewave', 'concept': 'Ehlers Even Better Sinewave (high-pass 40 + super smoother 10, normalized): wave ตัดขึ้นเหนือ −0.8 จากก้น → BUY (cycle low); ตัดลงใต้ +0.8 → SELL (cycle high)', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 20}


def generate(df, tf):
    c = df["close"].to_numpy(); n = len(c)
    a1 = (1 - np.sin(2 * np.pi / 40)) / np.cos(2 * np.pi / 40)
    hp = np.zeros(n)
    for i in range(1, n):
        hp[i] = 0.5 * (1 + a1) * (c[i] - c[i - 1]) + a1 * hp[i - 1]
    a = np.exp(-1.414 * np.pi / 10); b = 2 * a * np.cos(1.414 * np.pi / 10)
    c2, c3 = b, -a * a; c1 = 1 - c2 - c3
    f = np.zeros(n)
    for i in range(2, n):
        f[i] = c1 * (hp[i] + hp[i - 1]) / 2 + c2 * f[i - 1] + c3 * f[i - 2]
    fs = pd.Series(f, index=df.index)
    wave = (fs + fs.shift(1) + fs.shift(2)) / 3
    pwr = (fs ** 2 + fs.shift(1) ** 2 + fs.shift(2) ** 2) / 3
    w = wave / np.sqrt(pwr.replace(0, np.nan))
    ok = pd.Series(np.arange(n) > 100, index=df.index)
    return I.sig_from(I.cross_up(w, -0.8) & ok, I.cross_dn(w, 0.8) & ok)
