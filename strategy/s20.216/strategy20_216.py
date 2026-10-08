# -*- coding: utf-8 -*-
"""S20.216 — Stochastic Momentum Index Signal Cross

แนวคิด: William Blau SMI (10, 3, 3): ระยะ close จากกลางกรอบ HH/LL แบบ double-EMA ตัด signal EMA ขึ้นใต้ −40 → BUY; ตัดลงเหนือ +40 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.216', 'name': 'Stochastic Momentum Index Signal Cross', 'concept': 'William Blau SMI (10, 3, 3): ระยะ close จากกลางกรอบ HH/LL แบบ double-EMA ตัด signal EMA ขึ้นใต้ −40 → BUY; ตัดลงเหนือ +40 → SELL', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 20}


def generate(df, tf):
    hh, ll = I.highest(df["high"], 10), I.lowest(df["low"], 10)
    rel = df["close"] - (hh + ll) / 2
    smi = 100 * I.ema(I.ema(rel, 3), 3) / (0.5 * I.ema(I.ema(hh - ll, 3), 3)).replace(0, np.nan)
    sg = I.ema(smi, 3)
    return I.sig_from(I.cross_up(smi, sg) & (smi < -40), I.cross_dn(smi, sg) & (smi > 40))
