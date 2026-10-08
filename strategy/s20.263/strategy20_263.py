# -*- coding: utf-8 -*-
"""S20.263 — Rising/Falling Three Methods

แนวคิด: Rising Three Methods: เขียวยาว → 3 แท่งเล็กย่อตัวอยู่ในกรอบแท่งแรก → เขียวยาวปิดเหนือ close แท่งแรก → BUY continuation; Falling Three Methods → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.263', 'name': 'Rising/Falling Three Methods', 'concept': 'Rising Three Methods: เขียวยาว → 3 แท่งเล็กย่อตัวอยู่ในกรอบแท่งแรก → เขียวยาวปิดเหนือ close แท่งแรก → BUY continuation; Falling Three Methods → SELL', 'sl_atr': 1.2, 'rr': 2.0, 'max_hold': 20}


def generate(df, tf):
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    a = I.atr(df, 14)
    b4 = (c.shift(4) - o.shift(4))
    inner_in = ((h.shift(1).rolling(3).max() <= h.shift(4)) & (l.shift(1).rolling(3).min() >= l.shift(4)))
    small = ((c - o).abs().shift(1).rolling(3).max() < 0.5 * b4.abs())
    rise = (b4 > a) & inner_in & small & ((c - o) > a) & (c > c.shift(4))
    fall = (b4 < -a) & inner_in & small & ((o - c) > a) & (c < c.shift(4))
    return I.sig_from(rise, fall)
