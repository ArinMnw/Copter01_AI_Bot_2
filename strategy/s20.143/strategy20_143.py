# -*- coding: utf-8 -*-
"""S20.143 — Elder Impulse System Color Shift

แนวคิด: Elder Impulse: EMA13 ชันขึ้น + MACD histogram เพิ่มขึ้น = แท่งเขียว (กลับจากไม่เขียว) และอยู่เหนือ EMA65 (screen ใหญ่) → BUY; กลับด้านเป็นแดง → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.143', 'name': 'Elder Impulse System Color Shift', 'concept': 'Elder Impulse: EMA13 ชันขึ้น + MACD histogram เพิ่มขึ้น = แท่งเขียว (กลับจากไม่เขียว) และอยู่เหนือ EMA65 (screen ใหญ่) → BUY; กลับด้านเป็นแดง → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    e13 = I.ema(df["close"], 13)
    _, _, hist = I.macd(df["close"])
    green = (e13 > e13.shift(1)) & (hist > hist.shift(1))
    red = (e13 < e13.shift(1)) & (hist < hist.shift(1))
    e65 = I.ema(df["close"], 65)
    return I.sig_from(green & ~green.shift(1).fillna(False) & (df["close"] > e65) & (e65 > e65.shift(5)),
                      red & ~red.shift(1).fillna(False) & (df["close"] < e65) & (e65 < e65.shift(5)))
