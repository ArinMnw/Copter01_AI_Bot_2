# -*- coding: utf-8 -*-
"""S20.165 — Choppiness Index Regime Exit Breakout

แนวคิด: Choppiness Index(14) สูงกว่า 61.8 (ตลาดไซด์เวย์) แล้วตกลงต่ำกว่า 50 (เริ่ม trend) → เข้าตามทิศ close เทียบกลางกรอบ 14 แท่ง
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.165', 'name': 'Choppiness Index Regime Exit Breakout', 'concept': 'Choppiness Index(14) สูงกว่า 61.8 (ตลาดไซด์เวย์) แล้วตกลงต่ำกว่า 50 (เริ่ม trend) → เข้าตามทิศ close เทียบกลางกรอบ 14 แท่ง', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    n = 14
    hh, ll = I.highest(df["high"], n), I.lowest(df["low"], n)
    chop = 100 * np.log10(I.true_range(df).rolling(n).sum() / (hh - ll).replace(0, np.nan)) / np.log10(n)
    trig = (chop.shift(1).rolling(10).max() > 61.8) & I.cross_dn(chop, 50)
    mid = (hh + ll) / 2
    return I.sig_from(trig & (df["close"] > mid), trig & (df["close"] < mid))
