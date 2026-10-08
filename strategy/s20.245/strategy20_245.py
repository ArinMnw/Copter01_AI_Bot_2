# -*- coding: utf-8 -*-
"""S20.245 — DeMark Range Expansion Index Reversal

แนวคิด: TD REI(8): REI ต่ำกว่า −60 อย่างน้อย 3 แท่ง (oversold ที่ไม่ใช่ trend) แล้วตัดกลับขึ้นเหนือ −60 → BUY; > +60 แล้วตัดลง → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.245', 'name': 'DeMark Range Expansion Index Reversal', 'concept': 'TD REI(8): REI ต่ำกว่า −60 อย่างน้อย 3 แท่ง (oversold ที่ไม่ใช่ trend) แล้วตัดกลับขึ้นเหนือ −60 → BUY; > +60 แล้วตัดลง → SELL', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 20}


def generate(df, tf):
    h, l, c = df["high"], df["low"], df["close"]
    s1 = (h - h.shift(2)) + (l - l.shift(2))
    cond = ((h >= l.shift(5)) | (h >= l.shift(6))) & ((l <= h.shift(5)) | (l <= h.shift(6)))
    num = s1.where(cond, 0).rolling(8).sum()
    den = s1.abs().rolling(8).sum()
    rei = 100 * num / den.replace(0, np.nan)
    return I.sig_from(I.cross_up(rei, -60) & ((rei.shift(1) < -60).rolling(3).sum() == 3), I.cross_dn(rei, 60) & ((rei.shift(1) > 60).rolling(3).sum() == 3))
