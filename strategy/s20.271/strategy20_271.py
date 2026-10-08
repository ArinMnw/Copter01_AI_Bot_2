# -*- coding: utf-8 -*-
"""S20.271 — Heikin-Ashi Trend + Stochastic Pullback

แนวคิด: Heikin-Ashi เขียวติดกัน ≥ 5 แท่ง (trend ขึ้น) และ Stochastic(14) ย่อต่ำกว่า 30 แล้วตัดกลับขึ้น 30 → BUY ต่อ trend; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.271', 'name': 'Heikin-Ashi Trend + Stochastic Pullback', 'concept': 'Heikin-Ashi เขียวติดกัน ≥ 5 แท่ง (trend ขึ้น) และ Stochastic(14) ย่อต่ำกว่า 30 แล้วตัดกลับขึ้น 30 → BUY ต่อ trend; กลับด้าน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    ho, hh, hl, hc = I.heikin_ashi(df)
    bull = (hc > ho).astype(int); bear = (hc < ho).astype(int)
    k, d = I.stoch(df, 14, 3, 3)
    return I.sig_from((bull.shift(1).rolling(5).sum() == 5) & I.cross_up(k, 30), (bear.shift(1).rolling(5).sum() == 5) & I.cross_dn(k, 70))
