# -*- coding: utf-8 -*-
"""S20.162 — Ehlers Fisher Transform Reversal

แนวคิด: Ehlers Fisher Transform(10) ของ median price: Fisher ตัด trigger (ค่าก่อนหน้า) ขึ้นจากต่ำกว่า -1.5 → BUY; ตัดลงจากสูงกว่า +1.5 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.162', 'name': 'Ehlers Fisher Transform Reversal', 'concept': 'Ehlers Fisher Transform(10) ของ median price: Fisher ตัด trigger (ค่าก่อนหน้า) ขึ้นจากต่ำกว่า -1.5 → BUY; ตัดลงจากสูงกว่า +1.5 → SELL', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 20}


def generate(df, tf):
    med = ((df["high"] + df["low"]) / 2).to_numpy()
    n = len(med)
    hh = pd.Series(med).rolling(10).max().to_numpy(); ll = pd.Series(med).rolling(10).min().to_numpy()
    v = np.zeros(n); f = np.zeros(n)
    for i in range(1, n):
        rg = hh[i] - ll[i]
        x = 0.0 if not np.isfinite(rg) or rg == 0 else 2 * ((med[i] - ll[i]) / rg - 0.5)
        v[i] = np.clip(0.33 * x + 0.67 * v[i - 1], -0.999, 0.999)
        f[i] = 0.5 * np.log((1 + v[i]) / (1 - v[i])) + 0.5 * f[i - 1]
    fs = pd.Series(f, index=df.index); tg = fs.shift(1)
    return I.sig_from((fs > tg) & (fs.shift(1) <= tg.shift(1)) & (tg < -1.5), (fs < tg) & (fs.shift(1) >= tg.shift(1)) & (tg > 1.5))
