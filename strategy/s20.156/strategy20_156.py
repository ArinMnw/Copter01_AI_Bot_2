# -*- coding: utf-8 -*-
"""S20.156 — Chaikin Money Flow Zero-Line Thrust

แนวคิด: Chaikin Money Flow(20) (ใช้ tick volume) ตัดขึ้นเหนือ +0.05 จากใต้ศูนย์ภายใน 5 แท่ง + ราคาเหนือ EMA20 → BUY (accumulation เริ่ม); กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.156', 'name': 'Chaikin Money Flow Zero-Line Thrust', 'concept': 'Chaikin Money Flow(20) (ใช้ tick volume) ตัดขึ้นเหนือ +0.05 จากใต้ศูนย์ภายใน 5 แท่ง + ราคาเหนือ EMA20 → BUY (accumulation เริ่ม); กลับด้าน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    h, l, c, v = df["high"], df["low"], df["close"], df["volume"]
    mfm = ((c - l) - (h - c)) / (h - l).replace(0, np.nan)
    cmf = (mfm * v).rolling(20).sum() / v.rolling(20).sum()
    e20 = I.ema(c, 20)
    buy = I.cross_up(cmf, 0.05) & (cmf.rolling(5).min() < 0) & (c > e20)
    sell = I.cross_dn(cmf, -0.05) & (cmf.rolling(5).max() > 0) & (c < e20)
    return I.sig_from(buy, sell)
