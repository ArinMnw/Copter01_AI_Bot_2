# -*- coding: utf-8 -*-
"""S20.164 — Mass Index Reversal Bulge

แนวคิด: Donald Dorsey Mass Index (EMA9 ratio ของ range รวม 25): ขึ้นเกิน 27 แล้วลงต่ำกว่า 26.5 (reversal bulge) → เทรดสวนทิศของ EMA9 slope ก่อนหน้า (trend เดิมหมดแรง)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.164', 'name': 'Mass Index Reversal Bulge', 'concept': 'Donald Dorsey Mass Index (EMA9 ratio ของ range รวม 25): ขึ้นเกิน 27 แล้วลงต่ำกว่า 26.5 (reversal bulge) → เทรดสวนทิศของ EMA9 slope ก่อนหน้า (trend เดิมหมดแรง)', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 24}


def generate(df, tf):
    r = df["high"] - df["low"]
    e1 = I.ema(r, 9); e2 = I.ema(e1, 9)
    mi = (e1 / e2).rolling(25).sum()
    bulge = (mi.shift(1).rolling(10).max() > 27) & I.cross_dn(mi, 26.5)
    e9 = I.ema(df["close"], 9)
    tr_up = e9 > e9.shift(5)
    return I.sig_from(bulge & ~tr_up, bulge & tr_up)
