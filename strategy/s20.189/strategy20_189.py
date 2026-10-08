# -*- coding: utf-8 -*-
"""S20.189 — Disparity Index Z-Score Snapback

แนวคิด: Disparity index (close/EMA20 − 1) เทียบ z-score ย้อนหลัง 200 แท่ง: z < −2.5 แล้วแท่งปัจจุบันปิดเขียวกลับ (disparity ลดลง) → BUY; z > 2.5 ปิดแดง → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.189', 'name': 'Disparity Index Z-Score Snapback', 'concept': 'Disparity index (close/EMA20 − 1) เทียบ z-score ย้อนหลัง 200 แท่ง: z < −2.5 แล้วแท่งปัจจุบันปิดเขียวกลับ (disparity ลดลง) → BUY; z > 2.5 ปิดแดง → SELL', 'sl_atr': 1.5, 'rr': 1.2, 'max_hold': 16}


def generate(df, tf):
    c, o = df["close"], df["open"]
    di = c / I.ema(c, 20) - 1
    z = I.zscore(di, 200)
    return I.sig_from((z.shift(1) < -2.5) & (c > o) & (di > di.shift(1)), (z.shift(1) > 2.5) & (c < o) & (di < di.shift(1)))
