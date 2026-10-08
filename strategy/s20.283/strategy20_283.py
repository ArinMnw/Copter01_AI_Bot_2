# -*- coding: utf-8 -*-
"""S20.283 — TEMA / DEMA Cross

แนวคิด: Mulloy Triple EMA(10) ตัด Double EMA(30) ขึ้น → BUY; ตัดลง → SELL (MA ที่ลด lag สองระดับตัดกัน)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.283', 'name': 'TEMA / DEMA Cross', 'concept': 'Mulloy Triple EMA(10) ตัด Double EMA(30) ขึ้น → BUY; ตัดลง → SELL (MA ที่ลด lag สองระดับตัดกัน)', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    c = df["close"]
    e1 = I.ema(c, 10); e2 = I.ema(e1, 10); e3 = I.ema(e2, 10)
    tema = 3 * e1 - 3 * e2 + e3
    d1 = I.ema(c, 30); dema = 2 * d1 - I.ema(d1, 30)
    return I.sig_from(I.cross_up(tema, dema), I.cross_dn(tema, dema))
