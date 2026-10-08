# -*- coding: utf-8 -*-
"""S20.226 — Twiggs Money Flow Trend Filter

แนวคิด: Colin Twiggs Money Flow (true-range based, Wilder 21): ตัดขึ้นเหนือ 0 และอยู่เหนือค่าต่ำสุด 10 แท่ง + ราคาปิดทำ high 10 แท่ง → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.226', 'name': 'Twiggs Money Flow Trend Filter', 'concept': 'Colin Twiggs Money Flow (true-range based, Wilder 21): ตัดขึ้นเหนือ 0 และอยู่เหนือค่าต่ำสุด 10 แท่ง + ราคาปิดทำ high 10 แท่ง → BUY; กลับด้าน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    h, l, c, v = df["high"], df["low"], df["close"], df["volume"]
    th = pd.concat([h, c.shift(1)], axis=1).max(axis=1); tl = pd.concat([l, c.shift(1)], axis=1).min(axis=1)
    adv = ((c - tl) - (th - c)) / (th - tl).replace(0, np.nan) * v
    tmf = I.rma(adv.fillna(0), 21) / I.rma(v, 21)
    return I.sig_from((tmf > 0) & (tmf.shift(1) <= 0) & (c >= I.highest(c, 10)), (tmf < 0) & (tmf.shift(1) >= 0) & (c <= I.lowest(c, 10)))
