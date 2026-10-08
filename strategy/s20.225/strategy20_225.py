# -*- coding: utf-8 -*-
"""S20.225 — Chaikin Oscillator Zero Cross

แนวคิด: Chaikin Oscillator = EMA3 − EMA10 ของ Accumulation/Distribution line: ตัดศูนย์ขึ้นขณะ close > SMA50 → BUY; ตัดลงขณะ close < SMA50 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.225', 'name': 'Chaikin Oscillator Zero Cross', 'concept': 'Chaikin Oscillator = EMA3 − EMA10 ของ Accumulation/Distribution line: ตัดศูนย์ขึ้นขณะ close > SMA50 → BUY; ตัดลงขณะ close < SMA50 → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    h, l, c, v = df["high"], df["low"], df["close"], df["volume"]
    adl = (((c - l) - (h - c)) / (h - l).replace(0, np.nan) * v).fillna(0).cumsum()
    co = I.ema(adl, 3) - I.ema(adl, 10)
    s50 = I.sma(c, 50)
    return I.sig_from(I.cross_up(co, 0) & (c > s50), I.cross_dn(co, 0) & (c < s50))
