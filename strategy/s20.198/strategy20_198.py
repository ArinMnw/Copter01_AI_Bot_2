# -*- coding: utf-8 -*-
"""S20.198 — Random Walk Index Trend Confirmation

แนวคิด: Poulos Random Walk Index (8): RWI-high > 1.2 และตัดขึ้นเหนือ RWI-low (การเคลื่อนไหวเกินกว่า random walk) → BUY; RWI-low ตัดขึ้น → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.198', 'name': 'Random Walk Index Trend Confirmation', 'concept': 'Poulos Random Walk Index (8): RWI-high > 1.2 และตัดขึ้นเหนือ RWI-low (การเคลื่อนไหวเกินกว่า random walk) → BUY; RWI-low ตัดขึ้น → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    h, l = df["high"], df["low"]
    a = I.atr(df, 14)
    n = 8
    rh = pd.concat([(h - l.shift(k)) / (a * np.sqrt(k)) for k in range(2, n + 1)], axis=1).max(axis=1)
    rl = pd.concat([(h.shift(k) - l) / (a * np.sqrt(k)) for k in range(2, n + 1)], axis=1).max(axis=1)
    return I.sig_from(I.cross_up(rh, rl) & (rh > 1.2), I.cross_up(rl, rh) & (rl > 1.2))
