# -*- coding: utf-8 -*-
"""S20.161 — Ultimate Oscillator Williams Buy Setup

แนวคิด: Larry Williams Ultimate Oscillator (7/14/28): UO ลงต่ำกว่า 30 แล้วดีดกลับทะลุ high ของ UO ช่วง oversold → BUY; >70 แล้วหลุด low ช่วง overbought → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.161', 'name': 'Ultimate Oscillator Williams Buy Setup', 'concept': 'Larry Williams Ultimate Oscillator (7/14/28): UO ลงต่ำกว่า 30 แล้วดีดกลับทะลุ high ของ UO ช่วง oversold → BUY; >70 แล้วหลุด low ช่วง overbought → SELL', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 20}


def generate(df, tf):
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    bp = c - pd.concat([l, pc], axis=1).min(axis=1)
    tr = pd.concat([h, pc], axis=1).max(axis=1) - pd.concat([l, pc], axis=1).min(axis=1)
    avg = lambda n: bp.rolling(n).sum() / tr.rolling(n).sum()
    uo = 100 * (4 * avg(7) + 2 * avg(14) + avg(28)) / 7
    os_ = uo.rolling(10).min() < 30
    ob = uo.rolling(10).max() > 70
    buy = os_ & (uo > uo.shift(1).rolling(10).max()) & (uo < 50)
    sell = ob & (uo < uo.shift(1).rolling(10).min()) & (uo > 50)
    return I.sig_from(buy, sell)
