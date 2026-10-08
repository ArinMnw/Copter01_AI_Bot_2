# -*- coding: utf-8 -*-
"""S20.223 — Price-Volume Trend Signal Cross

แนวคิด: Price Volume Trend (Σ %Δclose × volume) ตัด signal EMA21 ขึ้น พร้อมราคาเหนือ EMA50 → BUY; ตัดลง + ใต้ EMA50 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.223', 'name': 'Price-Volume Trend Signal Cross', 'concept': 'Price Volume Trend (Σ %Δclose × volume) ตัด signal EMA21 ขึ้น พร้อมราคาเหนือ EMA50 → BUY; ตัดลง + ใต้ EMA50 → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    c = df["close"]
    pvt = (c.pct_change().fillna(0) * df["volume"]).cumsum()
    sg = I.ema(pvt, 21); e50 = I.ema(c, 50)
    return I.sig_from(I.cross_up(pvt, sg) & (c > e50), I.cross_dn(pvt, sg) & (c < e50))
