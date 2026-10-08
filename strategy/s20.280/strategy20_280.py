# -*- coding: utf-8 -*-
"""S20.280 — Market Facilitation Index Green Bar + Fractal

แนวคิด: Bill Williams MFI (range/volume): แท่ง 'Green' (MFI ขึ้นและ volume ขึ้น = ผู้เล่นใหม่เข้าตลาด) ที่ปิดทะลุ up-fractal ล่าสุด → BUY; ปิดหลุด down-fractal → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.280', 'name': 'Market Facilitation Index Green Bar + Fractal', 'concept': "Bill Williams MFI (range/volume): แท่ง 'Green' (MFI ขึ้นและ volume ขึ้น = ผู้เล่นใหม่เข้าตลาด) ที่ปิดทะลุ up-fractal ล่าสุด → BUY; ปิดหลุด down-fractal → SELL", 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    v = df["volume"].replace(0, np.nan)
    mfi = (df["high"] - df["low"]) / v
    green = (mfi > mfi.shift(1)) & (df["volume"] > df["volume"].shift(1))
    fu = I.confirmed_pivot_high(df, 2, 2).ffill(); fd = I.confirmed_pivot_low(df, 2, 2).ffill()
    c = df["close"]
    return I.sig_from(green & (c > fu) & (c.shift(1) <= fu.shift(1)), green & (c < fd) & (c.shift(1) >= fd.shift(1)))
