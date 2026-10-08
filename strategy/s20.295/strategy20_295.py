# -*- coding: utf-8 -*-
"""S20.295 — Expansion-Exhaustion Inside-Bar Fade

แนวคิด: 3 แท่งทิศเดียวกันที่ range ขยายต่อเนื่อง (แรงเร่งจนสุด) แล้วเกิด inside bar แรก → เข้าสวนทิศทันทีแท่งถัดไป (climax หมดแรง)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.295', 'name': 'Expansion-Exhaustion Inside-Bar Fade', 'concept': '3 แท่งทิศเดียวกันที่ range ขยายต่อเนื่อง (แรงเร่งจนสุด) แล้วเกิด inside bar แรก → เข้าสวนทิศทันทีแท่งถัดไป (climax หมดแรง)', 'sl_atr': 1.2, 'rr': 1.5, 'max_hold': 12}


def generate(df, tf):
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    r = h - l
    exp3 = (r.shift(1) > r.shift(2)) & (r.shift(2) > r.shift(3))
    up3 = (c.shift(1) > o.shift(1)) & (c.shift(2) > o.shift(2)) & (c.shift(3) > o.shift(3))
    dn3 = (c.shift(1) < o.shift(1)) & (c.shift(2) < o.shift(2)) & (c.shift(3) < o.shift(3))
    ib = (h < h.shift(1)) & (l > l.shift(1))
    return I.sig_from(ib & exp3 & dn3, ib & exp3 & up3)
