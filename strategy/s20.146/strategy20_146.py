# -*- coding: utf-8 -*-
"""S20.146 — Connors RSI-2 Trend Pullback

แนวคิด: Larry Connors RSI(2): อยู่เหนือ SMA200 และ RSI2<10 (ย่อสั้นๆ ใน uptrend) → BUY; ใต้ SMA200 และ RSI2>90 → SELL; mean-reversion เป้าใกล้ 1R
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.146', 'name': 'Connors RSI-2 Trend Pullback', 'concept': 'Larry Connors RSI(2): อยู่เหนือ SMA200 และ RSI2<10 (ย่อสั้นๆ ใน uptrend) → BUY; ใต้ SMA200 และ RSI2>90 → SELL; mean-reversion เป้าใกล้ 1R', 'sl_atr': 2.0, 'rr': 1.0, 'max_hold': 10}


def generate(df, tf):
    r2 = I.rsi(df["close"], 2)
    s200 = I.sma(df["close"], 200)
    return I.sig_from((df["close"] > s200) & (r2 < 10) & (r2.shift(1) >= 10),
                      (df["close"] < s200) & (r2 > 90) & (r2.shift(1) <= 90))
