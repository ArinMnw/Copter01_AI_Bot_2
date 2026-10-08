# -*- coding: utf-8 -*-
"""S20.170 — Williams %R Trend Pullback Hook

แนวคิด: Williams %R(14) ใน trend ของ EMA50>EMA200: %R ลงไปต่ำกว่า -80 แล้วตีกลับขึ้นเหนือ -50 ภายใน 5 แท่ง → BUY; downtrend ขึ้นเหนือ -20 แล้วกลับใต้ -50 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.170', 'name': 'Williams %R Trend Pullback Hook', 'concept': 'Williams %R(14) ใน trend ของ EMA50>EMA200: %R ลงไปต่ำกว่า -80 แล้วตีกลับขึ้นเหนือ -50 ภายใน 5 แท่ง → BUY; downtrend ขึ้นเหนือ -20 แล้วกลับใต้ -50 → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    hh, ll = I.highest(df["high"], 14), I.lowest(df["low"], 14)
    wr = -100 * (hh - df["close"]) / (hh - ll).replace(0, np.nan)
    e50, e200 = I.ema(df["close"], 50), I.ema(df["close"], 200)
    buy = (e50 > e200) & I.cross_up(wr, -50) & (wr.shift(1).rolling(5).min() < -80)
    sell = (e50 < e200) & I.cross_dn(wr, -50) & (wr.shift(1).rolling(5).max() > -20)
    return I.sig_from(buy, sell)
