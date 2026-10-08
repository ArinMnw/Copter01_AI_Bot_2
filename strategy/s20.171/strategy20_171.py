# -*- coding: utf-8 -*-
"""S20.171 — OBV Leading Breakout

แนวคิด: On-Balance Volume (tick volume) ทำ high ใหม่ 50 แท่งก่อนราคา (ราคายังไม่ทำ high ใหม่ แต่อยู่เหนือ EMA50) → BUY ล่วงหน้า; OBV ทำ low ใหม่ก่อนราคา → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.171', 'name': 'OBV Leading Breakout', 'concept': 'On-Balance Volume (tick volume) ทำ high ใหม่ 50 แท่งก่อนราคา (ราคายังไม่ทำ high ใหม่ แต่อยู่เหนือ EMA50) → BUY ล่วงหน้า; OBV ทำ low ใหม่ก่อนราคา → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    c = df["close"]
    obv = (np.sign(c.diff()).fillna(0) * df["volume"]).cumsum()
    ob_hi = obv >= I.highest(obv, 50); ob_lo = obv <= I.lowest(obv, 50)
    px_hi = df["high"] >= I.highest(df["high"], 50); px_lo = df["low"] <= I.lowest(df["low"], 50)
    e50 = I.ema(c, 50)
    buy = ob_hi & ~ob_hi.shift(1).fillna(False) & ~px_hi & (c > e50)
    sell = ob_lo & ~ob_lo.shift(1).fillna(False) & ~px_lo & (c < e50)
    return I.sig_from(buy, sell)
