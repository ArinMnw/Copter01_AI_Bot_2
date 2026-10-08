# -*- coding: utf-8 -*-
"""S20.191 — TD Sequential Perfected 9 Setup

แนวคิด: Tom DeMark TD Setup: ปิดต่ำกว่า close 4 แท่งก่อน 9 แท่งติด (Buy Setup) และ 'perfected' (low แท่ง 8 หรือ 9 ต่ำกว่า low แท่ง 6 และ 7) → BUY กลับตัว; Sell Setup กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.191', 'name': 'TD Sequential Perfected 9 Setup', 'concept': "Tom DeMark TD Setup: ปิดต่ำกว่า close 4 แท่งก่อน 9 แท่งติด (Buy Setup) และ 'perfected' (low แท่ง 8 หรือ 9 ต่ำกว่า low แท่ง 6 และ 7) → BUY กลับตัว; Sell Setup กลับด้าน → SELL", 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 20}


def generate(df, tf):
    c, h, l = df["close"], df["high"], df["low"]
    bs = (c < c.shift(4)).astype(int); ss = (c > c.shift(4)).astype(int)
    cb = bs.groupby((bs == 0).cumsum()).cumsum(); cs = ss.groupby((ss == 0).cumsum()).cumsum()
    perf_b = pd.concat([l, l.shift(1)], axis=1).min(axis=1) <= pd.concat([l.shift(2), l.shift(3)], axis=1).min(axis=1)
    perf_s = pd.concat([h, h.shift(1)], axis=1).max(axis=1) >= pd.concat([h.shift(2), h.shift(3)], axis=1).max(axis=1)
    return I.sig_from((cb == 9) & perf_b, (cs == 9) & perf_s)
