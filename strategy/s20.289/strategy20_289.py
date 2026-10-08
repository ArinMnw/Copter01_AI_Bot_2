# -*- coding: utf-8 -*-
"""S20.289 — SSL Channel Flip

แนวคิด: SSL Channel (SMA10 ของ high/low): ราคาปิดเหนือ SMA(high) → ช่องกลับเป็นขาขึ้น → BUY เมื่อ flip และราคาเหนือ EMA200; ใต้ SMA(low) → SELL เมื่อใต้ EMA200
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.289', 'name': 'SSL Channel Flip', 'concept': 'SSL Channel (SMA10 ของ high/low): ราคาปิดเหนือ SMA(high) → ช่องกลับเป็นขาขึ้น → BUY เมื่อ flip และราคาเหนือ EMA200; ใต้ SMA(low) → SELL เมื่อใต้ EMA200', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    sh, sl = I.sma(df["high"], 10), I.sma(df["low"], 10)
    c = df["close"].to_numpy(); hv, lv = sh.to_numpy(), sl.to_numpy()
    n = len(c); st = np.zeros(n, dtype=int)
    for i in range(1, n):
        st[i] = 1 if c[i] > hv[i] else (-1 if c[i] < lv[i] else st[i - 1])
    s = pd.Series(st, index=df.index)
    e200 = I.ema(df["close"], 200)
    return I.sig_from((s == 1) & (s.shift(1) == -1) & (df["close"] > e200), (s == -1) & (s.shift(1) == 1) & (df["close"] < e200))
