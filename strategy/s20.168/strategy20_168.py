# -*- coding: utf-8 -*-
"""S20.168 — Ehlers Super Smoother Crossover

แนวคิด: Ehlers 2-pole Super Smoother (10) ตัดกับ Super Smoother (40) — lag ต่ำกว่า EMA cross; เข้าเมื่อเส้นเร็วตัดขึ้น/ลง พร้อม slope ของเส้นช้าเห็นด้วย
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.168', 'name': 'Ehlers Super Smoother Crossover', 'concept': 'Ehlers 2-pole Super Smoother (10) ตัดกับ Super Smoother (40) — lag ต่ำกว่า EMA cross; เข้าเมื่อเส้นเร็วตัดขึ้น/ลง พร้อม slope ของเส้นช้าเห็นด้วย', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 40}


def generate(df, tf):
    def ss(x, p):
        x = x.to_numpy(); n = len(x); y = np.copy(x)
        a = np.exp(-1.414 * np.pi / p); b = 2 * a * np.cos(1.414 * np.pi / p)
        c2, c3 = b, -a * a; c1 = 1 - c2 - c3
        for i in range(2, n):
            y[i] = c1 * (x[i] + x[i - 1]) / 2 + c2 * y[i - 1] + c3 * y[i - 2]
        return pd.Series(y, index=df.index)
    f, s = ss(df["close"], 10), ss(df["close"], 40)
    w = pd.Series(np.arange(len(df)) >= 60, index=df.index)
    return I.sig_from(I.cross_up(f, s) & (s.diff() > 0) & w, I.cross_dn(f, s) & (s.diff() < 0) & w)
