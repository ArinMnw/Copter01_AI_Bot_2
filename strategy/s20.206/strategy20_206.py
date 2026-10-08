# -*- coding: utf-8 -*-
"""S20.206 — Keltner Band-Walk Continuation

แนวคิด: ปิดนอก Keltner บน (EMA20 ± 2 ATR) 3 แท่งติด = band walk (momentum สถาบัน) → BUY ต่อ; ปิดใต้ขอบล่าง 3 แท่งติด → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.206', 'name': 'Keltner Band-Walk Continuation', 'concept': 'ปิดนอก Keltner บน (EMA20 ± 2 ATR) 3 แท่งติด = band walk (momentum สถาบัน) → BUY ต่อ; ปิดใต้ขอบล่าง 3 แท่งติด → SELL', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 16}


def generate(df, tf):
    kl, km, ku = I.keltner(df, 20, 2.0)
    c = df["close"]
    ab = (c > ku).astype(int).rolling(3).sum() == 3
    bl = (c < kl).astype(int).rolling(3).sum() == 3
    return I.sig_from(ab & ~ab.shift(1).fillna(False), bl & ~bl.shift(1).fillna(False))
