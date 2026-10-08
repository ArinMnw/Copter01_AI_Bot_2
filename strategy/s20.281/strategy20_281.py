# -*- coding: utf-8 -*-
"""S20.281 — Zero-Lag EMA Cross

แนวคิด: Zero-Lag EMA (Ehlers/Way: EMA ของ 2·close − close[lag]) 12 ตัด 26 ขึ้น → BUY; ตัดลง → SELL (ลด lag เทียบ EMA cross ปกติ)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.281', 'name': 'Zero-Lag EMA Cross', 'concept': 'Zero-Lag EMA (Ehlers/Way: EMA ของ 2·close − close[lag]) 12 ตัด 26 ขึ้น → BUY; ตัดลง → SELL (ลด lag เทียบ EMA cross ปกติ)', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    c = df["close"]
    z = lambda n: I.ema(2 * c - c.shift((n - 1) // 2), n)
    f, s = z(12), z(26)
    return I.sig_from(I.cross_up(f, s), I.cross_dn(f, s))
