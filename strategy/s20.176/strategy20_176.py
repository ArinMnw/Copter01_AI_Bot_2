# -*- coding: utf-8 -*-
"""S20.176 — Morning Star / Evening Star at Band Extreme

แนวคิด: 3-candle Morning Star: แดงยาว → แท่งเล็ก (body<30% ของแท่งแรก) → เขียวปิดเกินครึ่งแท่งแรก ขณะแท่งแรกแตะ/ต่ำกว่า BB ล่าง(20,2) → BUY; Evening Star ที่ BB บน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.176', 'name': 'Morning Star / Evening Star at Band Extreme', 'concept': '3-candle Morning Star: แดงยาว → แท่งเล็ก (body<30% ของแท่งแรก) → เขียวปิดเกินครึ่งแท่งแรก ขณะแท่งแรกแตะ/ต่ำกว่า BB ล่าง(20,2) → BUY; Evening Star ที่ BB บน → SELL', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 20}


def generate(df, tf):
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    bd = (c - o)
    bl, _, bu = I.bbands(c, 20, 2.0)
    b1 = bd.shift(2); small = bd.shift(1).abs() < 0.3 * b1.abs()
    ms = (b1 < 0) & small & (bd > 0) & (c > o.shift(2) + b1 / 2) & (l.shift(2) <= bl.shift(2))
    es = (b1 > 0) & small & (bd < 0) & (c < o.shift(2) + b1 / 2) & (h.shift(2) >= bu.shift(2))
    return I.sig_from(ms, es)
