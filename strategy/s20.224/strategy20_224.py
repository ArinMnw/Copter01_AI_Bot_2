# -*- coding: utf-8 -*-
"""S20.224 — Volume-Weighted MACD Cross

แนวคิด: VW-MACD (Buff Dormeier): VWMA12 − VWMA26 ตัด signal EMA9 ขึ้นใต้ศูนย์ → BUY; ตัดลงเหนือศูนย์ → SELL (MACD ที่ถ่วงด้วย volume)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.224', 'name': 'Volume-Weighted MACD Cross', 'concept': 'VW-MACD (Buff Dormeier): VWMA12 − VWMA26 ตัด signal EMA9 ขึ้นใต้ศูนย์ → BUY; ตัดลงเหนือศูนย์ → SELL (MACD ที่ถ่วงด้วย volume)', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    c, v = df["close"], df["volume"]
    vw = lambda n: (c * v).rolling(n).sum() / v.rolling(n).sum()
    m = vw(12) - vw(26); sg = I.ema(m, 9)
    return I.sig_from(I.cross_up(m, sg) & (m < 0), I.cross_dn(m, sg) & (m > 0))
