# -*- coding: utf-8 -*-
"""S20.246 — DeMark TD Line Breakout

แนวคิด: TD Supply Line: ลากเส้นผ่าน TD point high 2 จุดล่าสุด (pivot 1/1 ที่ยืนยันแล้ว, จุดหลังต่ำกว่า) ราคาปิดทะลุเส้นนี้ขึ้นพร้อม qualifier (close ก่อนหน้า < close สองแท่งก่อน) → BUY; TD Demand line กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.246', 'name': 'DeMark TD Line Breakout', 'concept': 'TD Supply Line: ลากเส้นผ่าน TD point high 2 จุดล่าสุด (pivot 1/1 ที่ยืนยันแล้ว, จุดหลังต่ำกว่า) ราคาปิดทะลุเส้นนี้ขึ้นพร้อม qualifier (close ก่อนหน้า < close สองแท่งก่อน) → BUY; TD Demand line กลับด้าน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    ph = I.confirmed_pivot_high(df, 1, 1).to_numpy(); pl = I.confirmed_pivot_low(df, 1, 1).to_numpy()
    c = df["close"].to_numpy(); n = len(c); sig = np.zeros(n, dtype=np.int8)
    H = []; L = []
    for i in range(n):
        if np.isfinite(ph[i]):
            H = (H + [(i - 1, ph[i])])[-2:]
        if np.isfinite(pl[i]):
            L = (L + [(i - 1, pl[i])])[-2:]
        if i < 3:
            continue
        if len(H) == 2 and H[1][1] < H[0][1]:
            sl = (H[1][1] - H[0][1]) / (H[1][0] - H[0][0])
            ln, lp = H[1][1] + sl * (i - H[1][0]), H[1][1] + sl * (i - 1 - H[1][0])
            if c[i] > ln and c[i - 1] <= lp and c[i - 1] < c[i - 2]:
                sig[i] = 1; H = []
        if len(L) == 2 and L[1][1] > L[0][1]:
            sl = (L[1][1] - L[0][1]) / (L[1][0] - L[0][0])
            ln, lp = L[1][1] + sl * (i - L[1][0]), L[1][1] + sl * (i - 1 - L[1][0])
            if c[i] < ln and c[i - 1] >= lp and c[i - 1] > c[i - 2]:
                sig[i] = -1; L = []
    return sig
