# -*- coding: utf-8 -*-
"""S20.157 — KAMA Adaptive Slope Flip

แนวคิด: Kaufman Adaptive MA (ER10, fast2, slow30): KAMA เปลี่ยนจากลงเป็นขึ้น (slope flip เกิน 0.05 ATR) และ Efficiency Ratio > 0.3 → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.157', 'name': 'KAMA Adaptive Slope Flip', 'concept': 'Kaufman Adaptive MA (ER10, fast2, slow30): KAMA เปลี่ยนจากลงเป็นขึ้น (slope flip เกิน 0.05 ATR) และ Efficiency Ratio > 0.3 → BUY; กลับด้าน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 40}


def generate(df, tf):
    c = df["close"].to_numpy()
    n = len(c)
    er = np.full(n, np.nan); k = np.full(n, np.nan)
    chg = np.abs(c[10:] - c[:-10])
    vol = pd.Series(np.abs(np.diff(c, prepend=c[0]))).rolling(10).sum().to_numpy()
    er[10:] = chg / np.where(vol[10:] == 0, np.nan, vol[10:])
    fast, slow = 2 / 3, 2 / 31
    sc = (np.nan_to_num(er) * (fast - slow) + slow) ** 2
    kama = np.full(n, np.nan)
    if n > 11:
        kama[10] = c[10]
        for i in range(11, n):
            kama[i] = kama[i - 1] + sc[i] * (c[i] - kama[i - 1])
    ks = pd.Series(kama, index=df.index); ers = pd.Series(er, index=df.index)
    d = ks.diff(); a = I.atr(df, 14)
    buy = (d > 0.05 * a) & (d.shift(1) <= 0) & (ers > 0.3)
    sell = (d < -0.05 * a) & (d.shift(1) >= 0) & (ers > 0.3)
    return I.sig_from(buy, sell)
