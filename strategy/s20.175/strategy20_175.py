# -*- coding: utf-8 -*-
"""S20.175 — Three Soldiers / Three Crows Continuation

แนวคิด: 3 แท่งเขียวติด แต่ละแท่ง open ในเนื้อแท่งก่อน ปิดใกล้ high (ไส้บน<25%) และ close สูงขึ้นทุกแท่ง (Three White Soldiers) → BUY; Three Black Crows → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.175', 'name': 'Three Soldiers / Three Crows Continuation', 'concept': '3 แท่งเขียวติด แต่ละแท่ง open ในเนื้อแท่งก่อน ปิดใกล้ high (ไส้บน<25%) และ close สูงขึ้นทุกแท่ง (Three White Soldiers) → BUY; Three Black Crows → SELL', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 20}


def generate(df, tf):
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    rg = (h - l).replace(0, np.nan)
    g = (c > o) & ((h - c) / rg < 0.25) & ((c - o) / rg > 0.5)
    r = (c < o) & ((c - l) / rg < 0.25) & ((o - c) / rg > 0.5)
    ws = g & g.shift(1) & g.shift(2) & (c > c.shift(1)) & (c.shift(1) > c.shift(2)) & (o > o.shift(1)) & (o <= c.shift(1))
    bc = r & r.shift(1) & r.shift(2) & (c < c.shift(1)) & (c.shift(1) < c.shift(2)) & (o < o.shift(1)) & (o >= c.shift(1))
    return I.sig_from(ws.fillna(False), bc.fillna(False))
