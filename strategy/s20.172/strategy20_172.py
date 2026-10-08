# -*- coding: utf-8 -*-
"""S20.172 — Elder Force Index Pullback in EMA22 Trend

แนวคิด: Elder: EMA22 ชันขึ้น และ Force Index EMA2 (Δราคา×volume) ติดลบ = ย่อในขาขึ้น เมื่อ FI2 กลับเป็นบวก → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.172', 'name': 'Elder Force Index Pullback in EMA22 Trend', 'concept': 'Elder: EMA22 ชันขึ้น และ Force Index EMA2 (Δราคา×volume) ติดลบ = ย่อในขาขึ้น เมื่อ FI2 กลับเป็นบวก → BUY; กลับด้าน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    c = df["close"]
    fi2 = I.ema(c.diff() * df["volume"], 2)
    e22 = I.ema(c, 22)
    up = e22 > e22.shift(3); dn = e22 < e22.shift(3)
    return I.sig_from(up & (fi2 > 0) & (fi2.shift(1) < 0) & (fi2.shift(2) < 0), dn & (fi2 < 0) & (fi2.shift(1) > 0) & (fi2.shift(2) > 0))
