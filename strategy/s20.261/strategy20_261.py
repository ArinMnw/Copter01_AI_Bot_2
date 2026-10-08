# -*- coding: utf-8 -*-
"""S20.261 — Three Inside Up/Down Confirmation

แนวคิด: Three Inside Up: แดงยาว → harami เขียวอยู่ในเนื้อ → แท่งที่ 3 ปิดเหนือ open ของแท่งแดง (ยืนยัน) → BUY; Three Inside Down กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.261', 'name': 'Three Inside Up/Down Confirmation', 'concept': 'Three Inside Up: แดงยาว → harami เขียวอยู่ในเนื้อ → แท่งที่ 3 ปิดเหนือ open ของแท่งแดง (ยืนยัน) → BUY; Three Inside Down กลับด้าน → SELL', 'sl_atr': 1.2, 'rr': 1.5, 'max_hold': 16}


def generate(df, tf):
    o, c = df["open"], df["close"]
    a = I.atr(df, 14)
    big_r = (c.shift(2) < o.shift(2)) & ((o.shift(2) - c.shift(2)) > a)
    big_g = (c.shift(2) > o.shift(2)) & ((c.shift(2) - o.shift(2)) > a)
    har_g = (c.shift(1) > o.shift(1)) & (o.shift(1) > c.shift(2)) & (c.shift(1) < o.shift(2))
    har_r = (c.shift(1) < o.shift(1)) & (o.shift(1) < c.shift(2)) & (c.shift(1) > o.shift(2))
    return I.sig_from(big_r & har_g & (c > o.shift(2)), big_g & har_r & (c < o.shift(2)))
