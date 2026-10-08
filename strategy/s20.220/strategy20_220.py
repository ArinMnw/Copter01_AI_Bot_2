# -*- coding: utf-8 -*-
"""S20.220 — Trend Intensity Index Threshold

แนวคิด: M.H. Pee Trend Intensity Index (SMA60, 30 แท่ง) = % ของ deviation บวก: ตัดขึ้นเหนือ 80 → BUY (trend ขึ้นเข้ม); ตัดลงใต้ 20 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.220', 'name': 'Trend Intensity Index Threshold', 'concept': 'M.H. Pee Trend Intensity Index (SMA60, 30 แท่ง) = % ของ deviation บวก: ตัดขึ้นเหนือ 80 → BUY (trend ขึ้นเข้ม); ตัดลงใต้ 20 → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    c = df["close"]
    dev = c - I.sma(c, 60)
    pos = dev.clip(lower=0).rolling(30).sum(); neg = (-dev).clip(lower=0).rolling(30).sum()
    tii = 100 * pos / (pos + neg).replace(0, np.nan)
    return I.sig_from(I.cross_up(tii, 80), I.cross_dn(tii, 20))
