# -*- coding: utf-8 -*-
"""S20.186 — Five-Close Exhaustion Streak Fade

แนวคิด: ปิดสูงขึ้น 5 แท่งติดต่อกัน + RSI14 > 70 = วิ่งยืดเกิน → SELL สวน; ปิดต่ำลง 5 แท่งติด + RSI14 < 30 → BUY
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.186', 'name': 'Five-Close Exhaustion Streak Fade', 'concept': 'ปิดสูงขึ้น 5 แท่งติดต่อกัน + RSI14 > 70 = วิ่งยืดเกิน → SELL สวน; ปิดต่ำลง 5 แท่งติด + RSI14 < 30 → BUY', 'sl_atr': 1.5, 'rr': 1.0, 'max_hold': 12}


def generate(df, tf):
    c = df["close"]
    up = (c > c.shift(1)).astype(int); dn = (c < c.shift(1)).astype(int)
    r = I.rsi(c, 14)
    return I.sig_from((dn.rolling(5).sum() == 5) & (r < 30), (up.rolling(5).sum() == 5) & (r > 70))
