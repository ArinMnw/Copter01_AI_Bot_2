# -*- coding: utf-8 -*-
"""S20.278 — Elder-Ray Bear-Power Recovery

แนวคิด: Elder-Ray: EMA13 ชันขึ้น, Bear Power (low − EMA13) ติดลบแต่เพิ่มขึ้นจากแท่งก่อน (แรงขายอ่อนลง) และ Bull Power ทำ high ใหม่ 5 แท่ง → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.278', 'name': 'Elder-Ray Bear-Power Recovery', 'concept': 'Elder-Ray: EMA13 ชันขึ้น, Bear Power (low − EMA13) ติดลบแต่เพิ่มขึ้นจากแท่งก่อน (แรงขายอ่อนลง) และ Bull Power ทำ high ใหม่ 5 แท่ง → BUY; กลับด้าน → SELL', 'sl_atr': 1.2, 'rr': 2.0, 'max_hold': 20}


def generate(df, tf):
    e = I.ema(df["close"], 13)
    bull = df["high"] - e; bear = df["low"] - e
    buy = (e > e.shift(1)) & (bear < 0) & (bear > bear.shift(1)) & (bull >= bull.rolling(5).max())
    sell = (e < e.shift(1)) & (bull > 0) & (bull < bull.shift(1)) & (bear <= bear.rolling(5).min())
    return I.sig_from(buy, sell)
