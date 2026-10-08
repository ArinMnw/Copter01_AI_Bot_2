# -*- coding: utf-8 -*-
"""S20.188 — Regression R² Trend Emergence

แนวคิด: R² ของ linear regression 50 แท่งพุ่งจาก < 0.3 (สุ่ม) เป็น > 0.75 ภายใน 20 แท่ง = trend เพิ่งเกิด → เข้าตามทิศ slope
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.188', 'name': 'Regression R² Trend Emergence', 'concept': 'R² ของ linear regression 50 แท่งพุ่งจาก < 0.3 (สุ่ม) เป็น > 0.75 ภายใน 20 แท่ง = trend เพิ่งเกิด → เข้าตามทิศ slope', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    c = df["close"]
    r2 = I.linreg_r2(c, 50)
    sl = I.linreg_slope(c, 50)
    em = I.cross_up(r2, 0.75) & (r2.shift(1).rolling(20).min() < 0.3)
    return I.sig_from(em & (sl > 0), em & (sl < 0))
