# -*- coding: utf-8 -*-
"""S20.227 — A/D Line Breakout Ahead of Price

แนวคิด: Accumulation/Distribution line ทำ high ใหม่ 40 แท่งขณะราคาอยู่ต่ำกว่า high 40 แท่ง > 0.5 ATR (สะสมของก่อนราคาวิ่ง) → BUY; ADL ทำ low ใหม่ → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.227', 'name': 'A/D Line Breakout Ahead of Price', 'concept': 'Accumulation/Distribution line ทำ high ใหม่ 40 แท่งขณะราคาอยู่ต่ำกว่า high 40 แท่ง > 0.5 ATR (สะสมของก่อนราคาวิ่ง) → BUY; ADL ทำ low ใหม่ → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    h, l, c, v = df["high"], df["low"], df["close"], df["volume"]
    adl = (((c - l) - (h - c)) / (h - l).replace(0, np.nan) * v).fillna(0).cumsum()
    a = I.atr(df, 14)
    nh = (adl >= I.highest(adl, 40)) & ~(adl.shift(1) >= I.highest(adl, 40).shift(1))
    nl = (adl <= I.lowest(adl, 40)) & ~(adl.shift(1) <= I.lowest(adl, 40).shift(1))
    return I.sig_from(nh & (I.highest(h, 40) - c > 0.5 * a), nl & (c - I.lowest(l, 40) > 0.5 * a))
