# -*- coding: utf-8 -*-
"""S20.195 — Relative Vigor Index Cross

แนวคิด: Relative Vigor Index(10): (close−open)/(high−low) แบบ symmetric-weighted ตัด signal ขึ้นขณะ RVI < 0 → BUY; ตัดลงขณะ RVI > 0 → SELL (แท่งปิดแข็งแรงกว่า open)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.195', 'name': 'Relative Vigor Index Cross', 'concept': 'Relative Vigor Index(10): (close−open)/(high−low) แบบ symmetric-weighted ตัด signal ขึ้นขณะ RVI < 0 → BUY; ตัดลงขณะ RVI > 0 → SELL (แท่งปิดแข็งแรงกว่า open)', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    sw = lambda s: (s + 2 * s.shift(1) + 2 * s.shift(2) + s.shift(3)) / 6
    rvi = sw(c - o).rolling(10).sum() / sw(h - l).rolling(10).sum()
    sg = sw(rvi)
    return I.sig_from(I.cross_up(rvi, sg) & (rvi < 0), I.cross_dn(rvi, sg) & (rvi > 0))
