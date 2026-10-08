# -*- coding: utf-8 -*-
"""S20.292 — HalfTrend Direction Change

แนวคิด: HalfTrend (amplitude 2): ติดตาม max ของ low / min ของ high 2 แท่ง ร่วมกับ SMA ของ high/low — ทิศเปลี่ยนเป็นขึ้น → BUY; เปลี่ยนเป็นลง → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.292', 'name': 'HalfTrend Direction Change', 'concept': 'HalfTrend (amplitude 2): ติดตาม max ของ low / min ของ high 2 แท่ง ร่วมกับ SMA ของ high/low — ทิศเปลี่ยนเป็นขึ้น → BUY; เปลี่ยนเป็นลง → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    h, l, c = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    hs = I.sma(df["high"], 2).to_numpy(); ls = I.sma(df["low"], 2).to_numpy()
    hh = pd.Series(h).rolling(2).max().to_numpy(); ll = pd.Series(l).rolling(2).min().to_numpy()
    n = len(c); tr = np.zeros(n, dtype=int); sig = np.zeros(n, dtype=np.int8)
    max_low, min_high = l[0], h[0]
    for i in range(2, n):
        tr[i] = tr[i - 1]
        if tr[i - 1] == 0:
            max_low = max(ll[i], max_low)
            if hs[i] < max_low and c[i] < l[i - 1]:
                tr[i] = 1; min_high = hh[i]
        else:
            min_high = min(hh[i], min_high)
            if ls[i] > min_high and c[i] > h[i - 1]:
                tr[i] = 0; max_low = ll[i]
        if tr[i] != tr[i - 1]:
            sig[i] = 1 if tr[i] == 0 else -1
    return sig
