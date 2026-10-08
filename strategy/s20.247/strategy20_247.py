# -*- coding: utf-8 -*-
"""S20.247 — DeMark TD Countdown 13 Exhaustion

แนวคิด: TD Countdown: หลัง TD Buy Setup 9 เสร็จ นับแท่งที่ close ≤ low 2 แท่งก่อน (ไม่ต้องติดกัน) ครบ 13 → BUY exhaustion; Sell Countdown กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.247', 'name': 'DeMark TD Countdown 13 Exhaustion', 'concept': 'TD Countdown: หลัง TD Buy Setup 9 เสร็จ นับแท่งที่ close ≤ low 2 แท่งก่อน (ไม่ต้องติดกัน) ครบ 13 → BUY exhaustion; Sell Countdown กลับด้าน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    c, h, l = df["close"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy()
    n = len(c); sig = np.zeros(n, dtype=np.int8)
    bs = ss = 0; bc = sc = -1
    for i in range(4, n):
        bs = bs + 1 if c[i] < c[i - 4] else 0
        ss = ss + 1 if c[i] > c[i - 4] else 0
        if bs == 9:
            bc, sc = 0, -1
        if ss == 9:
            sc, bc = 0, -1
        if bc >= 0 and c[i] <= l[i - 2]:
            bc += 1
            if bc == 13:
                sig[i] = 1; bc = -1
        if sc >= 0 and c[i] >= h[i - 2]:
            sc += 1
            if sc == 13:
                sig[i] = -1; sc = -1
    return sig
