# -*- coding: utf-8 -*-
"""S20.286 — ALMA Cross (Arnaud Legoux)

แนวคิด: ALMA 9 (offset 0.85, sigma 6) ตัด ALMA 34 ขึ้น → BUY; ตัดลง → SELL (Gaussian-weighted MA ที่ลด lag และ noise)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.286', 'name': 'ALMA Cross (Arnaud Legoux)', 'concept': 'ALMA 9 (offset 0.85, sigma 6) ตัด ALMA 34 ขึ้น → BUY; ตัดลง → SELL (Gaussian-weighted MA ที่ลด lag และ noise)', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    def alma(x, n, off=0.85, sig=6):
        m = off * (n - 1); s = n / sig
        w = np.exp(-((np.arange(n) - m) ** 2) / (2 * s * s)); w /= w.sum()
        return x.rolling(n).apply(lambda y: np.dot(w, y), raw=True)
    f, s = alma(df["close"], 9), alma(df["close"], 34)
    return I.sig_from(I.cross_up(f, s), I.cross_dn(f, s))
