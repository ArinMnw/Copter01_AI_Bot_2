# -*- coding: utf-8 -*-
"""S20.217 — Intraday Momentum Index Extremes

แนวคิด: Tushar Chande IMI(14) = RSI ที่ใช้เนื้อเทียน (close−open) แทน close−close: ตัดขึ้นจาก < 30 → BUY; ตัดลงจาก > 70 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.217', 'name': 'Intraday Momentum Index Extremes', 'concept': 'Tushar Chande IMI(14) = RSI ที่ใช้เนื้อเทียน (close−open) แทน close−close: ตัดขึ้นจาก < 30 → BUY; ตัดลงจาก > 70 → SELL', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 20}


def generate(df, tf):
    b = df["close"] - df["open"]
    up = b.clip(lower=0).rolling(14).sum(); dn = (-b).clip(lower=0).rolling(14).sum()
    imi = 100 * up / (up + dn).replace(0, np.nan)
    return I.sig_from(I.cross_up(imi, 30), I.cross_dn(imi, 70))
