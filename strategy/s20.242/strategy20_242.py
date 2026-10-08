# -*- coding: utf-8 -*-
"""S20.242 — Rainbow MA Full Alignment

แนวคิด: Mel Widner Rainbow: SMA2 ซ้อนกัน 10 ชั้น (SMA ของ SMA) — ราคาปิดเหนือทุกชั้นและชั้นเรียงจากเร็วไปช้าครบครั้งแรก → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.242', 'name': 'Rainbow MA Full Alignment', 'concept': 'Mel Widner Rainbow: SMA2 ซ้อนกัน 10 ชั้น (SMA ของ SMA) — ราคาปิดเหนือทุกชั้นและชั้นเรียงจากเร็วไปช้าครบครั้งแรก → BUY; กลับด้าน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    c = df["close"]
    layers = []; x = c
    for _ in range(10):
        x = I.sma(x, 2); layers.append(x)
    R = pd.concat(layers, axis=1)
    ordered_up = (R.diff(axis=1).iloc[:, 1:] < 0).all(axis=1)
    ordered_dn = (R.diff(axis=1).iloc[:, 1:] > 0).all(axis=1)
    bull = (c > R.max(axis=1)) & ordered_up
    bear = (c < R.min(axis=1)) & ordered_dn
    return I.sig_from(bull & ~bull.shift(1).fillna(False), bear & ~bear.shift(1).fillna(False))
