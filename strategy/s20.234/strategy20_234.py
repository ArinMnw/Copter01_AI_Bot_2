# -*- coding: utf-8 -*-
"""S20.234 — Head & Shoulders Neckline Break (confirmed pivots)

แนวคิด: Head & Shoulders จาก pivot high/low ที่ยืนยันแล้ว (3/3): pivot high 3 จุดล่าสุด หัวสูงสุด ไหล่ซ้าย-ขวาต่างกัน < 0.5 ATR แล้วราคาปิดหลุด neckline (low ต่ำสุดระหว่างไหล่) → SELL; Inverse H&S → BUY
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.234', 'name': 'Head & Shoulders Neckline Break (confirmed pivots)', 'concept': 'Head & Shoulders จาก pivot high/low ที่ยืนยันแล้ว (3/3): pivot high 3 จุดล่าสุด หัวสูงสุด ไหล่ซ้าย-ขวาต่างกัน < 0.5 ATR แล้วราคาปิดหลุด neckline (low ต่ำสุดระหว่างไหล่) → SELL; Inverse H&S → BUY', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    ph = I.confirmed_pivot_high(df, 3, 3).to_numpy(); pl = I.confirmed_pivot_low(df, 3, 3).to_numpy()
    c = df["close"].to_numpy(); a = I.atr(df, 14).to_numpy()
    n = len(c); sig = np.zeros(n, dtype=np.int8)
    H, L = [], []
    neck_s = neck_b = np.nan
    for i in range(n):
        if np.isfinite(ph[i]):
            H.append(ph[i]); H = H[-3:]
            if len(H) == 3 and H[1] > H[0] and H[1] > H[2] and abs(H[0] - H[2]) < 0.5 * a[i] and L:
                neck_s = min(L[-2:])
        if np.isfinite(pl[i]):
            L.append(pl[i]); L = L[-3:]
            if len(L) == 3 and L[1] < L[0] and L[1] < L[2] and abs(L[0] - L[2]) < 0.5 * a[i] and H:
                neck_b = max(H[-2:])
        if np.isfinite(neck_s) and c[i] < neck_s:
            sig[i] = -1; neck_s = np.nan
        elif np.isfinite(neck_b) and c[i] > neck_b:
            sig[i] = 1; neck_b = np.nan
    return sig
