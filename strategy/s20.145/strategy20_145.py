# -*- coding: utf-8 -*-
"""S20.145 — Raschke Holy Grail ADX Pullback

แนวคิด: Linda Raschke Holy Grail: ADX14>30 และยังขึ้น (trend แรง) ราคาย่อแตะ EMA20 แล้วปิดกลับเหนือ EMA20 ฝั่ง +DI>-DI → BUY (กลับด้านสำหรับ SELL)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.145', 'name': 'Raschke Holy Grail ADX Pullback', 'concept': 'Linda Raschke Holy Grail: ADX14>30 และยังขึ้น (trend แรง) ราคาย่อแตะ EMA20 แล้วปิดกลับเหนือ EMA20 ฝั่ง +DI>-DI → BUY (กลับด้านสำหรับ SELL)', 'sl_atr': 1.2, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    pdi, ndi, adx = I.dmi(df, 14)
    e20 = I.ema(df["close"], 20)
    strong = (adx > 30) & (adx.shift(3) < adx)
    buy = strong & (pdi > ndi) & (df["low"] <= e20) & (df["close"] > e20)
    sell = strong & (ndi > pdi) & (df["high"] >= e20) & (df["close"] < e20)
    return I.sig_from(buy, sell)
