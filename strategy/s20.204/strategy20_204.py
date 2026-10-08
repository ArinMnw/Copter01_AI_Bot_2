# -*- coding: utf-8 -*-
"""S20.204 — Guppy Multiple MA Separation

แนวคิด: Daryl Guppy GMMA: EMA กลุ่มสั้น (3,5,8,10,12,15) อยู่เหนือกลุ่มยาว (30,35,40,45,50,60) ทั้งหมด ครั้งแรกหลังพันกัน และกลุ่มยาวเรียงขึ้น → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.204', 'name': 'Guppy Multiple MA Separation', 'concept': 'Daryl Guppy GMMA: EMA กลุ่มสั้น (3,5,8,10,12,15) อยู่เหนือกลุ่มยาว (30,35,40,45,50,60) ทั้งหมด ครั้งแรกหลังพันกัน และกลุ่มยาวเรียงขึ้น → BUY; กลับด้าน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 40}


def generate(df, tf):
    c = df["close"]
    sh = pd.concat([I.ema(c, n) for n in (3, 5, 8, 10, 12, 15)], axis=1)
    lg = pd.concat([I.ema(c, n) for n in (30, 35, 40, 45, 50, 60)], axis=1)
    bull = sh.min(axis=1) > lg.max(axis=1)
    bear = sh.max(axis=1) < lg.min(axis=1)
    lg_up = lg.iloc[:, 0] > lg.iloc[:, -1]
    return I.sig_from(bull & ~bull.shift(1).fillna(False) & lg_up, bear & ~bear.shift(1).fillna(False) & ~lg_up)
