# -*- coding: utf-8 -*-
"""S20.147 — NR7 Volatility-Contraction Breakout

แนวคิด: Toby Crabel NR7: แท่งก่อนหน้าเป็นแท่ง range แคบที่สุดใน 7 แท่ง แท่งปัจจุบันปิดทะลุ high/low ของแท่ง NR7 → เข้าตามทิศ (expansion หลัง contraction)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.147', 'name': 'NR7 Volatility-Contraction Breakout', 'concept': 'Toby Crabel NR7: แท่งก่อนหน้าเป็นแท่ง range แคบที่สุดใน 7 แท่ง แท่งปัจจุบันปิดทะลุ high/low ของแท่ง NR7 → เข้าตามทิศ (expansion หลัง contraction)', 'sl_atr': 1.0, 'rr': 2.0, 'max_hold': 20}


def generate(df, tf):
    r = df["high"] - df["low"]
    nr7 = r == r.rolling(7).min()
    p = nr7.shift(1).fillna(False)
    return I.sig_from(p & (df["close"] > df["high"].shift(1)), p & (df["close"] < df["low"].shift(1)))
