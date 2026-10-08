# -*- coding: utf-8 -*-
"""S20.222 — Negative Volume Index Smart-Money Trend

แนวคิด: Norman Fosback NVI: เปลี่ยนเฉพาะแท่งที่ volume ลดลง (smart money) — NVI ตัดขึ้นเหนือ EMA255 ของตัวเอง → BUY; ตัดลง → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.222', 'name': 'Negative Volume Index Smart-Money Trend', 'concept': 'Norman Fosback NVI: เปลี่ยนเฉพาะแท่งที่ volume ลดลง (smart money) — NVI ตัดขึ้นเหนือ EMA255 ของตัวเอง → BUY; ตัดลง → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 40}


def generate(df, tf):
    c, v = df["close"], df["volume"]
    r = c.pct_change().where(v < v.shift(1), 0.0).fillna(0.0)
    nvi = 1000 * (1 + r).cumprod()
    e = I.ema(nvi, 255)
    return I.sig_from(I.cross_up(nvi, e), I.cross_dn(nvi, e))
