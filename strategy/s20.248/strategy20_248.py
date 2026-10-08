# -*- coding: utf-8 -*-
"""S20.248 — Elder Triple Screen

แนวคิด: Elder Triple Screen: screen 1 = EMA(65) slope (≈ weekly EMA13 บน TF ย่อย), screen 2 = Stochastic(5) < 30 ใน uptrend, screen 3 = ราคาปิดทะลุ high แท่งก่อน → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.248', 'name': 'Elder Triple Screen', 'concept': 'Elder Triple Screen: screen 1 = EMA(65) slope (≈ weekly EMA13 บน TF ย่อย), screen 2 = Stochastic(5) < 30 ใน uptrend, screen 3 = ราคาปิดทะลุ high แท่งก่อน → BUY; กลับด้าน → SELL', 'sl_atr': 1.2, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    c, h, l = df["close"], df["high"], df["low"]
    e = I.ema(c, 65)
    k, d = I.stoch(df, 5, 3, 3)
    up = e > e.shift(3); dn = e < e.shift(3)
    return I.sig_from(up & (d.shift(1) < 30) & (c > h.shift(1)), dn & (d.shift(1) > 70) & (c < l.shift(1)))
