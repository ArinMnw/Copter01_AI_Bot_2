# -*- coding: utf-8 -*-
"""S20.257 — Doji Indecision after Trend Run

แนวคิด: แท่ง Doji (body < 10% range, range ≥ 0.8 ATR) หลังปิดทิศเดียวกัน 4 แท่งติด แล้วแท่งถัดไปปิดสวนทาง (ยืนยัน) → เข้าตามทิศแท่งยืนยัน
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.257', 'name': 'Doji Indecision after Trend Run', 'concept': 'แท่ง Doji (body < 10% range, range ≥ 0.8 ATR) หลังปิดทิศเดียวกัน 4 แท่งติด แล้วแท่งถัดไปปิดสวนทาง (ยืนยัน) → เข้าตามทิศแท่งยืนยัน', 'sl_atr': 1.2, 'rr': 1.5, 'max_hold': 16}


def generate(df, tf):
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    a = I.atr(df, 14)
    doji = ((c - o).abs() < 0.1 * (h - l)) & ((h - l) >= 0.8 * a)
    up4 = (c.shift(2) > o.shift(2)) & (c.shift(3) > o.shift(3)) & (c.shift(4) > o.shift(4)) & (c.shift(5) > o.shift(5))
    dn4 = (c.shift(2) < o.shift(2)) & (c.shift(3) < o.shift(3)) & (c.shift(4) < o.shift(4)) & (c.shift(5) < o.shift(5))
    d1 = doji.shift(1).fillna(False)
    return I.sig_from(d1 & dn4 & (c > h.shift(1)), d1 & up4 & (c < l.shift(1)))
