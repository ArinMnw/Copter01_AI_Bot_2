# -*- coding: utf-8 -*-
"""S20.262 — Three Outside Up/Down

แนวคิด: Three Outside Up: แท่งแดง → แท่งเขียวกลืนทั้งเนื้อ (outside) → แท่งที่ 3 ปิดสูงกว่า close แท่งเขียว → BUY; Three Outside Down → SELL (ใช้ยืนยันแท่งที่ 3 ต่างจาก engulf แท่งเดียว)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.262', 'name': 'Three Outside Up/Down', 'concept': 'Three Outside Up: แท่งแดง → แท่งเขียวกลืนทั้งเนื้อ (outside) → แท่งที่ 3 ปิดสูงกว่า close แท่งเขียว → BUY; Three Outside Down → SELL (ใช้ยืนยันแท่งที่ 3 ต่างจาก engulf แท่งเดียว)', 'sl_atr': 1.2, 'rr': 1.5, 'max_hold': 16}


def generate(df, tf):
    o, c = df["open"], df["close"]
    eng_u = (c.shift(2) < o.shift(2)) & (c.shift(1) > o.shift(1)) & (c.shift(1) > o.shift(2)) & (o.shift(1) < c.shift(2))
    eng_d = (c.shift(2) > o.shift(2)) & (c.shift(1) < o.shift(1)) & (c.shift(1) < o.shift(2)) & (o.shift(1) > c.shift(2))
    return I.sig_from(eng_u & (c > c.shift(1)) & (c > o), eng_d & (c < c.shift(1)) & (c < o))
