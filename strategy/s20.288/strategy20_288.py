# -*- coding: utf-8 -*-
"""S20.288 — Gann HiLo Activator Flip

แนวคิด: Gann HiLo Activator (SMA3 ของ high/low แท่งก่อน): ราคาปิดเหนือ SMA3(high) → เปลี่ยนเป็นขาขึ้น (BUY เมื่อ flip), ปิดใต้ SMA3(low) → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.288', 'name': 'Gann HiLo Activator Flip', 'concept': 'Gann HiLo Activator (SMA3 ของ high/low แท่งก่อน): ราคาปิดเหนือ SMA3(high) → เปลี่ยนเป็นขาขึ้น (BUY เมื่อ flip), ปิดใต้ SMA3(low) → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    hs, ls = I.sma(df["high"], 3).shift(1), I.sma(df["low"], 3).shift(1)
    c = df["close"].to_numpy(); hv, lv = hs.to_numpy(), ls.to_numpy()
    n = len(c); st = np.zeros(n, dtype=int); sig = np.zeros(n, dtype=np.int8)
    for i in range(1, n):
        st[i] = 1 if c[i] > hv[i] else (-1 if c[i] < lv[i] else st[i - 1])
        if st[i] != st[i - 1] and st[i - 1] != 0:
            sig[i] = st[i]
    return sig
