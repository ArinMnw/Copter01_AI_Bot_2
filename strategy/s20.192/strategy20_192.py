# -*- coding: utf-8 -*-
"""S20.192 — DeMarker Oscillator Extreme Re-entry

แนวคิด: Tom DeMark DeMarker(14): ตกต่ำกว่า 0.3 แล้วตัดกลับขึ้นเหนือ 0.3 → BUY; ขึ้นเกิน 0.7 แล้วตัดกลับลง → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.192', 'name': 'DeMarker Oscillator Extreme Re-entry', 'concept': 'Tom DeMark DeMarker(14): ตกต่ำกว่า 0.3 แล้วตัดกลับขึ้นเหนือ 0.3 → BUY; ขึ้นเกิน 0.7 แล้วตัดกลับลง → SELL', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 20}


def generate(df, tf):
    h, l = df["high"], df["low"]
    dmx = (h - h.shift(1)).clip(lower=0); dmn = (l.shift(1) - l).clip(lower=0)
    dem = I.sma(dmx, 14) / (I.sma(dmx, 14) + I.sma(dmn, 14)).replace(0, np.nan)
    return I.sig_from(I.cross_up(dem, 0.3), I.cross_dn(dem, 0.7))
