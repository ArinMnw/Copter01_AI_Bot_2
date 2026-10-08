# -*- coding: utf-8 -*-
"""S20.255 — Hikkake Inside-Bar False Breakout

แนวคิด: Dan Chesler Hikkake: inside bar → แท่งถัดไปหลุด low ของ inside bar (false breakout ลง) → ภายใน 3 แท่งราคาปิดเหนือ high ของ inside bar → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.255', 'name': 'Hikkake Inside-Bar False Breakout', 'concept': 'Dan Chesler Hikkake: inside bar → แท่งถัดไปหลุด low ของ inside bar (false breakout ลง) → ภายใน 3 แท่งราคาปิดเหนือ high ของ inside bar → BUY; กลับด้าน → SELL', 'sl_atr': 1.2, 'rr': 2.0, 'max_hold': 20}


def generate(df, tf):
    h, l, c = df["high"], df["low"], df["close"]
    ib = (h < h.shift(1)) & (l > l.shift(1))
    n = len(df); sig = np.zeros(n, dtype=np.int8)
    ibv = ib.to_numpy(); hv, lv, cv = h.to_numpy(), l.to_numpy(), c.to_numpy()
    pend = None
    for i in range(2, n):
        if pend is not None:
            d, lvl, exp = pend
            if d == 1 and cv[i] > lvl:
                sig[i] = 1; pend = None
            elif d == -1 and cv[i] < lvl:
                sig[i] = -1; pend = None
            elif i >= exp:
                pend = None
        if ibv[i - 1] and pend is None:
            if lv[i] < lv[i - 1] and hv[i] <= hv[i - 1]:
                pend = (1, hv[i - 1], i + 3)
            elif hv[i] > hv[i - 1] and lv[i] >= lv[i - 1]:
                pend = (-1, lv[i - 1], i + 3)
    return sig
