# -*- coding: utf-8 -*-
"""S20.218 — Relative Momentum Index Pullback

แนวคิด: Roger Altman RMI(14, momentum 5) = RSI ของการเปลี่ยนแปลง 5 แท่ง: ใน uptrend (EMA50 ขึ้น) RMI ย่อต่ำกว่า 40 แล้วตัดกลับขึ้น 40 → BUY; downtrend ตัดลงใต้ 60 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.218', 'name': 'Relative Momentum Index Pullback', 'concept': 'Roger Altman RMI(14, momentum 5) = RSI ของการเปลี่ยนแปลง 5 แท่ง: ใน uptrend (EMA50 ขึ้น) RMI ย่อต่ำกว่า 40 แล้วตัดกลับขึ้น 40 → BUY; downtrend ตัดลงใต้ 60 → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    d = df["close"].diff(5)
    up = I.rma(d.clip(lower=0), 14); dn = I.rma((-d).clip(lower=0), 14)
    rmi = 100 * up / (up + dn).replace(0, np.nan)
    e = I.ema(df["close"], 50)
    return I.sig_from(I.cross_up(rmi, 40) & (e > e.shift(5)), I.cross_dn(rmi, 60) & (e < e.shift(5)))
