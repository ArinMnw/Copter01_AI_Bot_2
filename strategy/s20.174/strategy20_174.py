# -*- coding: utf-8 -*-
"""S20.174 — Klinger Volume Oscillator Signal Cross

แนวคิด: Klinger Oscillator (volume force EMA34−EMA55) ตัด signal EMA13 ขึ้นใต้ศูนย์ → BUY; ตัดลงเหนือศูนย์ → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.174', 'name': 'Klinger Volume Oscillator Signal Cross', 'concept': 'Klinger Oscillator (volume force EMA34−EMA55) ตัด signal EMA13 ขึ้นใต้ศูนย์ → BUY; ตัดลงเหนือศูนย์ → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    h, l, c, v = df["high"], df["low"], df["close"], df["volume"]
    hlc = h + l + c
    trend = np.where(hlc > hlc.shift(1), 1, -1)
    vf = pd.Series(v * trend, index=df.index)
    ko = I.ema(vf, 34) - I.ema(vf, 55)
    sg = I.ema(ko, 13)
    return I.sig_from(I.cross_up(ko, sg) & (ko < 0), I.cross_dn(ko, sg) & (ko > 0))
