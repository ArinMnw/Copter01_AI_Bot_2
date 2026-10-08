# -*- coding: utf-8 -*-
"""S20.287 — Trend Trigger Factor

แนวคิด: M.H. Pee Trend Trigger Factor (15): เทียบแรงซื้อ (HH ล่าสุด − LL ก่อนหน้า) กับแรงขาย ตัดขึ้นเหนือ +100 → BUY; ตัดลงใต้ −100 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.287', 'name': 'Trend Trigger Factor', 'concept': 'M.H. Pee Trend Trigger Factor (15): เทียบแรงซื้อ (HH ล่าสุด − LL ก่อนหน้า) กับแรงขาย ตัดขึ้นเหนือ +100 → BUY; ตัดลงใต้ −100 → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    h, l = df["high"], df["low"]; n = 15
    hh_r, ll_r = I.highest(h, n), I.lowest(l, n)
    hh_p, ll_p = hh_r.shift(n), ll_r.shift(n)
    bp = hh_r - ll_p; sp = hh_p - ll_r
    ttf = 200 * (bp - sp) / (bp + sp).replace(0, np.nan)
    return I.sig_from(I.cross_up(ttf, 100), I.cross_dn(ttf, -100))
