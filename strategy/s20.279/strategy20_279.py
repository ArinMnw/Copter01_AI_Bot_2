# -*- coding: utf-8 -*-
"""S20.279 — Ichimoku Kijun-sen Bounce

แนวคิด: ราคาอยู่เหนือ Kijun (26) มา ≥ 10 แท่ง ย่อลงแตะ Kijun (low ≤ Kijun) แต่ปิดเหนือ และ Kijun แบน/ขึ้น → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.279', 'name': 'Ichimoku Kijun-sen Bounce', 'concept': 'ราคาอยู่เหนือ Kijun (26) มา ≥ 10 แท่ง ย่อลงแตะ Kijun (low ≤ Kijun) แต่ปิดเหนือ และ Kijun แบน/ขึ้น → BUY; กลับด้าน → SELL', 'sl_atr': 1.0, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    h, l, c = df["high"], df["low"], df["close"]
    kij = (I.highest(h, 26) + I.lowest(l, 26)) / 2
    ab = (c.shift(1) > kij.shift(1)).rolling(10).sum() == 10
    be = (c.shift(1) < kij.shift(1)).rolling(10).sum() == 10
    return I.sig_from(ab & (l <= kij) & (c > kij) & (kij >= kij.shift(3)), be & (h >= kij) & (c < kij) & (kij <= kij.shift(3)))
