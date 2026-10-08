# -*- coding: utf-8 -*-
"""S20.272 — Keltner-Midline RSI-50 Reclaim

แนวคิด: ราคาอยู่เหนือกลาง Keltner (EMA20) และ RSI14 ตัดกลับขึ้นเหนือ 50 หลังย่อลงต่ำกว่า 45 ใน 5 แท่ง → BUY (reclaim momentum กลางกรอบ); กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.272', 'name': 'Keltner-Midline RSI-50 Reclaim', 'concept': 'ราคาอยู่เหนือกลาง Keltner (EMA20) และ RSI14 ตัดกลับขึ้นเหนือ 50 หลังย่อลงต่ำกว่า 45 ใน 5 แท่ง → BUY (reclaim momentum กลางกรอบ); กลับด้าน → SELL', 'sl_atr': 1.2, 'rr': 2.0, 'max_hold': 20}


def generate(df, tf):
    kl, km, ku = I.keltner(df, 20, 1.5)
    r = I.rsi(df["close"], 14)
    c = df["close"]
    return I.sig_from((c > km) & I.cross_up(r, 50) & (r.shift(1).rolling(5).min() < 45), (c < km) & I.cross_dn(r, 50) & (r.shift(1).rolling(5).max() > 55))
