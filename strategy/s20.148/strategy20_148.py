# -*- coding: utf-8 -*-
"""S20.148 — Inside-Bar Mother-Bar Breakout with EMA50 Trend

แนวคิด: แท่ง i-1 เป็น inside bar ของ mother bar (i-2) แท่ง i ปิดทะลุ high/low ของ mother bar ในทิศเดียวกับ EMA50 slope → เข้าตาม trend
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.148', 'name': 'Inside-Bar Mother-Bar Breakout with EMA50 Trend', 'concept': 'แท่ง i-1 เป็น inside bar ของ mother bar (i-2) แท่ง i ปิดทะลุ high/low ของ mother bar ในทิศเดียวกับ EMA50 slope → เข้าตาม trend', 'sl_atr': 1.2, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    h, l, c = df["high"], df["low"], df["close"]
    ib = (h.shift(1) < h.shift(2)) & (l.shift(1) > l.shift(2))
    e50 = I.ema(c, 50)
    up = e50 > e50.shift(5)
    return I.sig_from(ib & (c > h.shift(2)) & up, ib & (c < l.shift(2)) & ~up)
