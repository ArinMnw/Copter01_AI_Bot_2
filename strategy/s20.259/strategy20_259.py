# -*- coding: utf-8 -*-
"""S20.259 — Piercing Line / Dark Cloud Cover

แนวคิด: Piercing: แท่งแดงยาว (> 1 ATR) ตามด้วยแท่งเปิดใต้ close แท่งแดงแล้วปิดเกินกึ่งกลางเนื้อแท่งแดง (แต่ไม่กลืน) → BUY; Dark Cloud Cover กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.259', 'name': 'Piercing Line / Dark Cloud Cover', 'concept': 'Piercing: แท่งแดงยาว (> 1 ATR) ตามด้วยแท่งเปิดใต้ close แท่งแดงแล้วปิดเกินกึ่งกลางเนื้อแท่งแดง (แต่ไม่กลืน) → BUY; Dark Cloud Cover กลับด้าน → SELL', 'sl_atr': 1.2, 'rr': 1.5, 'max_hold': 16}


def generate(df, tf):
    o, c = df["open"], df["close"]
    a = I.atr(df, 14)
    mid = (o.shift(1) + c.shift(1)) / 2
    pierce = (c.shift(1) < o.shift(1)) & ((o.shift(1) - c.shift(1)) > a) & (o < c.shift(1)) & (c > mid) & (c < o.shift(1))
    dark = (c.shift(1) > o.shift(1)) & ((c.shift(1) - o.shift(1)) > a) & (o > c.shift(1)) & (c < mid) & (c > o.shift(1))
    return I.sig_from(pierce, dark)
