# -*- coding: utf-8 -*-
"""S20.243 — Polarized Fractal Efficiency Surge

แนวคิด: Hannula PFE(10, smoothing EMA5): ตัดขึ้นเหนือ +50 (เส้นทางราคาตรงและขึ้น) → BUY; ตัดลงใต้ −50 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.243', 'name': 'Polarized Fractal Efficiency Surge', 'concept': 'Hannula PFE(10, smoothing EMA5): ตัดขึ้นเหนือ +50 (เส้นทางราคาตรงและขึ้น) → BUY; ตัดลงใต้ −50 → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    c = df["close"]; n = 10
    straight = np.sqrt((c - c.shift(n)) ** 2 + n ** 2)
    path = np.sqrt(c.diff() ** 2 + 1).rolling(n).sum()
    pfe = I.ema(100 * np.sign(c - c.shift(n)) * straight / path, 5)
    return I.sig_from(I.cross_up(pfe, 50), I.cross_dn(pfe, -50))
