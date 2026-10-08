# -*- coding: utf-8 -*-
"""S20.275 — Median-Filter Trend Flip

แนวคิด: Rolling median 21 แท่ง (ทนต่อ spike กว่าค่าเฉลี่ย) เปลี่ยนจากลดลงเป็นเพิ่มขึ้น 3 แท่งติด → BUY; เพิ่มเป็นลด 3 แท่งติด → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.275', 'name': 'Median-Filter Trend Flip', 'concept': 'Rolling median 21 แท่ง (ทนต่อ spike กว่าค่าเฉลี่ย) เปลี่ยนจากลดลงเป็นเพิ่มขึ้น 3 แท่งติด → BUY; เพิ่มเป็นลด 3 แท่งติด → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    md = df["close"].rolling(21).median()
    d = np.sign(md.diff())
    up3 = (d == 1) & (d.shift(1) == 1) & (d.shift(2) == 1) & (d.shift(3) <= 0)
    dn3 = (d == -1) & (d.shift(1) == -1) & (d.shift(2) == -1) & (d.shift(3) >= 0)
    return I.sig_from(up3, dn3)
