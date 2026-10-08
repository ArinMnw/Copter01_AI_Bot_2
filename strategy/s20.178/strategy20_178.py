# -*- coding: utf-8 -*-
"""S20.178 — Raschke 80-20 Reversal

แนวคิด: Linda Raschke 80-20: แท่งก่อนหน้าเปิดใน 20% บนของ range และปิดใน 20% ล่าง (ขายหนัก) แท่งปัจจุบันทำ low ต่ำกว่าแล้วปิดกลับเหนือ low แท่งก่อน → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.178', 'name': 'Raschke 80-20 Reversal', 'concept': 'Linda Raschke 80-20: แท่งก่อนหน้าเปิดใน 20% บนของ range และปิดใน 20% ล่าง (ขายหนัก) แท่งปัจจุบันทำ low ต่ำกว่าแล้วปิดกลับเหนือ low แท่งก่อน → BUY; กลับด้าน → SELL', 'sl_atr': 1.0, 'rr': 1.5, 'max_hold': 12}


def generate(df, tf):
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    rg = (h - l).replace(0, np.nan)
    pos_o = (o - l) / rg; pos_c = (c - l) / rg
    b8020 = (pos_o.shift(1) >= 0.8) & (pos_c.shift(1) <= 0.2)
    s8020 = (pos_o.shift(1) <= 0.2) & (pos_c.shift(1) >= 0.8)
    return I.sig_from(b8020 & (l < l.shift(1)) & (c > l.shift(1)), s8020 & (h > h.shift(1)) & (c < h.shift(1)))
