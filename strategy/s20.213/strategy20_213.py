# -*- coding: utf-8 -*-
"""S20.213 — MACD Zero-Line Cross with EMA200 Regime

แนวคิด: MACD(12,26) ตัดเส้นศูนย์ขึ้น (EMA12 > EMA26 ครั้งแรก) ขณะราคาเหนือ EMA200 และ signal line ชันขึ้น → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.213', 'name': 'MACD Zero-Line Cross with EMA200 Regime', 'concept': 'MACD(12,26) ตัดเส้นศูนย์ขึ้น (EMA12 > EMA26 ครั้งแรก) ขณะราคาเหนือ EMA200 และ signal line ชันขึ้น → BUY; กลับด้าน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 40}


def generate(df, tf):
    m, sg, _ = I.macd(df["close"])
    e200 = I.ema(df["close"], 200)
    return I.sig_from(I.cross_up(m, 0) & (df["close"] > e200) & (sg > sg.shift(1)), I.cross_dn(m, 0) & (df["close"] < e200) & (sg < sg.shift(1)))
