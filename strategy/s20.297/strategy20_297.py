# -*- coding: utf-8 -*-
"""S20.297 — Pretty Good Oscillator Breakout

แนวคิด: Mark Johnson Pretty Good Oscillator = (close − SMA14)/EMA14(TR): ตัดขึ้นเหนือ +3 → BUY (breakout ที่มีนัย); ตัดลงใต้ −3 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.297', 'name': 'Pretty Good Oscillator Breakout', 'concept': 'Mark Johnson Pretty Good Oscillator = (close − SMA14)/EMA14(TR): ตัดขึ้นเหนือ +3 → BUY (breakout ที่มีนัย); ตัดลงใต้ −3 → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    c = df["close"]
    pgo = (c - I.sma(c, 14)) / I.ema(I.true_range(df), 14)
    return I.sig_from(I.cross_up(pgo, 3), I.cross_dn(pgo, -3))
