# -*- coding: utf-8 -*-
"""S20.166 — True Strength Index Signal Cross

แนวคิด: William Blau TSI (25/13) ตัด signal EMA7 ขึ้นขณะ TSI < -10 → BUY; ตัดลงขณะ TSI > 10 → SELL (double-smoothed momentum)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.166', 'name': 'True Strength Index Signal Cross', 'concept': 'William Blau TSI (25/13) ตัด signal EMA7 ขึ้นขณะ TSI < -10 → BUY; ตัดลงขณะ TSI > 10 → SELL (double-smoothed momentum)', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    d = df["close"].diff()
    tsi = 100 * I.ema(I.ema(d, 25), 13) / I.ema(I.ema(d.abs(), 25), 13)
    sg = I.ema(tsi, 7)
    return I.sig_from(I.cross_up(tsi, sg) & (tsi < -10), I.cross_dn(tsi, sg) & (tsi > 10))
