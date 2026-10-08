# -*- coding: utf-8 -*-
"""S20.190 — Psychological Line Sentiment Extreme

แนวคิด: Psychological Line PSY(12) = % แท่งปิดขึ้นใน 12 แท่ง: ≤ 25% (มองร้ายสุด) ขณะ close > SMA200 → BUY; ≥ 75% ขณะ close < SMA200 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.190', 'name': 'Psychological Line Sentiment Extreme', 'concept': 'Psychological Line PSY(12) = % แท่งปิดขึ้นใน 12 แท่ง: ≤ 25% (มองร้ายสุด) ขณะ close > SMA200 → BUY; ≥ 75% ขณะ close < SMA200 → SELL', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 20}


def generate(df, tf):
    c = df["close"]
    psy = 100 * (c > c.shift(1)).astype(float).rolling(12).mean()
    s200 = I.sma(c, 200)
    return I.sig_from(I.cross_up(psy, 25) & (c > s200), I.cross_dn(psy, 75) & (c < s200))
