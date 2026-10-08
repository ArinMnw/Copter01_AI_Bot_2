# -*- coding: utf-8 -*-
"""S20.276 — Chande Forecast Oscillator Flip

แนวคิด: Chande Forecast Oscillator = % ระยะ close จาก linear-regression forecast (14): เปลี่ยนจากลบเป็นบวก 2 แท่งติด ขณะ slope regression 50 ขึ้น → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.276', 'name': 'Chande Forecast Oscillator Flip', 'concept': 'Chande Forecast Oscillator = % ระยะ close จาก linear-regression forecast (14): เปลี่ยนจากลบเป็นบวก 2 แท่งติด ขณะ slope regression 50 ขึ้น → BUY; กลับด้าน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    c = df["close"]; n = 14
    x = np.arange(n, dtype=float)
    fc = c.rolling(n).apply(lambda y: np.polyval(np.polyfit(x, y, 1), n - 1), raw=True)
    cfo = 100 * (c - fc.shift(1)) / c
    sl = I.linreg_slope(c, 50)
    return I.sig_from((cfo > 0) & (cfo.shift(1) > 0) & (cfo.shift(2) <= 0) & (sl > 0), (cfo < 0) & (cfo.shift(1) < 0) & (cfo.shift(2) >= 0) & (sl < 0))
