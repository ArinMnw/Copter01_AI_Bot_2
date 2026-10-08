# -*- coding: utf-8 -*-
"""S20.228 — Low-Volume Pullback in Trend

แนวคิด: Trend (EMA20 > EMA50 และทั้งคู่ชันขึ้น) ย่อ 3 แท่งด้วย tick volume ต่ำกว่าค่าเฉลี่ย 20 แท่ง (ไม่มีแรงขาย) แล้วแท่งถัดมาปิดเหนือ high แท่งก่อนด้วย volume สูงขึ้น → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.228', 'name': 'Low-Volume Pullback in Trend', 'concept': 'Trend (EMA20 > EMA50 และทั้งคู่ชันขึ้น) ย่อ 3 แท่งด้วย tick volume ต่ำกว่าค่าเฉลี่ย 20 แท่ง (ไม่มีแรงขาย) แล้วแท่งถัดมาปิดเหนือ high แท่งก่อนด้วย volume สูงขึ้น → BUY; กลับด้าน → SELL', 'sl_atr': 1.2, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
    e20, e50 = I.ema(c, 20), I.ema(c, 50)
    av = I.sma(v, 20)
    up = (e20 > e50) & (e20 > e20.shift(3)); dn = (e20 < e50) & (e20 < e20.shift(3))
    pb_d = (c.shift(1) < c.shift(2)) & (c.shift(2) < c.shift(3)) & (v.shift(1) < av) & (v.shift(2) < av) & (v.shift(3) < av)
    pb_u = (c.shift(1) > c.shift(2)) & (c.shift(2) > c.shift(3)) & (v.shift(1) < av) & (v.shift(2) < av) & (v.shift(3) < av)
    return I.sig_from(up & pb_d & (c > h.shift(1)) & (v > v.shift(1)), dn & pb_u & (c < l.shift(1)) & (v > v.shift(1)))
