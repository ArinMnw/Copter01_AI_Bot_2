# -*- coding: utf-8 -*-
"""S20.241 — Ehlers Center of Gravity Oscillator Cross

แนวคิด: Ehlers Center of Gravity (10): ตำแหน่งถ่วงน้ำหนักของราคา 10 แท่ง ตัด trigger (ค่าก่อนหน้า) ขึ้นใน 20% ล่างของกรอบ 50 แท่ง → BUY; ตัดลงใน 20% บน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.241', 'name': 'Ehlers Center of Gravity Oscillator Cross', 'concept': 'Ehlers Center of Gravity (10): ตำแหน่งถ่วงน้ำหนักของราคา 10 แท่ง ตัด trigger (ค่าก่อนหน้า) ขึ้นใน 20% ล่างของกรอบ 50 แท่ง → BUY; ตัดลงใน 20% บน → SELL', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 20}


def generate(df, tf):
    p = (df["high"] + df["low"]) / 2
    w = np.arange(1, 11, dtype=float)
    cg = p.rolling(10).apply(lambda x: -np.dot(w, x[::-1]) / x.sum(), raw=True)
    tg = cg.shift(1)
    lo, hi = cg.rolling(50).min(), cg.rolling(50).max()
    pos = (cg - lo) / (hi - lo).replace(0, np.nan)
    return I.sig_from((cg > tg) & (cg.shift(1) <= tg.shift(1)) & (pos < 0.2), (cg < tg) & (cg.shift(1) >= tg.shift(1)) & (pos > 0.8))
