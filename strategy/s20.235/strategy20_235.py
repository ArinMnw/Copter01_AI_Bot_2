# -*- coding: utf-8 -*-
"""S20.235 — Double Bottom/Top Neckline Break

แนวคิด: W-bottom: pivot low 2 จุดล่าสุดห่างกัน ≤ 0.3 ATR และ pivot high ระหว่างกลางสูงกว่า ≥ 1.5 ATR; ราคาปิดทะลุ pivot high กลาง → BUY; M-top กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.235', 'name': 'Double Bottom/Top Neckline Break', 'concept': 'W-bottom: pivot low 2 จุดล่าสุดห่างกัน ≤ 0.3 ATR และ pivot high ระหว่างกลางสูงกว่า ≥ 1.5 ATR; ราคาปิดทะลุ pivot high กลาง → BUY; M-top กลับด้าน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    ph = I.confirmed_pivot_high(df, 3, 3).to_numpy(); pl = I.confirmed_pivot_low(df, 3, 3).to_numpy()
    c = df["close"].to_numpy(); a = I.atr(df, 14).to_numpy()
    n = len(c); sig = np.zeros(n, dtype=np.int8)
    lastH = lastL = np.nan; prevH = prevL = np.nan; midH_after_L = np.nan; midL_after_H = np.nan
    lvl_b = lvl_s = np.nan
    for i in range(n):
        if np.isfinite(ph[i]):
            prevH, lastH = lastH, ph[i]; midH_after_L = ph[i]
            if np.isfinite(prevH) and abs(lastH - prevH) <= 0.3 * a[i] and np.isfinite(midL_after_H) and lastH - midL_after_H >= 1.5 * a[i]:
                lvl_s = midL_after_H
        if np.isfinite(pl[i]):
            prevL, lastL = lastL, pl[i]; midL_after_H = pl[i]
            if np.isfinite(prevL) and abs(lastL - prevL) <= 0.3 * a[i] and np.isfinite(midH_after_L) and midH_after_L - lastL >= 1.5 * a[i]:
                lvl_b = midH_after_L
        if np.isfinite(lvl_b) and c[i] > lvl_b:
            sig[i] = 1; lvl_b = np.nan
        elif np.isfinite(lvl_s) and c[i] < lvl_s:
            sig[i] = -1; lvl_s = np.nan
    return sig
