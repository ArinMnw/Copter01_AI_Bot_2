# -*- coding: utf-8 -*-
"""S20.251 — Inside-NR4 Straddle (ID/NR4)

แนวคิด: Street Smarts ID/NR4: แท่งก่อนหน้าเป็นทั้ง inside bar และ range แคบสุดใน 4 แท่ง แท่งปัจจุบันปิดนอกกรอบแท่งนั้นทางใด → เข้าทางนั้น (volatility expansion จากจุดบีบสุด)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.251', 'name': 'Inside-NR4 Straddle (ID/NR4)', 'concept': 'Street Smarts ID/NR4: แท่งก่อนหน้าเป็นทั้ง inside bar และ range แคบสุดใน 4 แท่ง แท่งปัจจุบันปิดนอกกรอบแท่งนั้นทางใด → เข้าทางนั้น (volatility expansion จากจุดบีบสุด)', 'sl_atr': 1.0, 'rr': 2.0, 'max_hold': 16}


def generate(df, tf):
    h, l, c = df["high"], df["low"], df["close"]
    r = h - l
    idnr4 = (h < h.shift(1)) & (l > l.shift(1)) & (r == r.rolling(4).min())
    p = idnr4.shift(1).fillna(False)
    return I.sig_from(p & (c > h.shift(1)), p & (c < l.shift(1)))
