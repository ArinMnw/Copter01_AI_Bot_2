# -*- coding: utf-8 -*-
"""S20.177 — Tweezer Bottom/Top at 20-Bar Extreme

แนวคิด: สองแท่งติดกันมี low เท่ากัน (ห่าง ≤0.05 ATR) ที่เป็น low ต่ำสุด 20 แท่ง แท่งแรกแดง แท่งสองเขียว → Tweezer Bottom BUY; กลับด้าน Tweezer Top SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.177', 'name': 'Tweezer Bottom/Top at 20-Bar Extreme', 'concept': 'สองแท่งติดกันมี low เท่ากัน (ห่าง ≤0.05 ATR) ที่เป็น low ต่ำสุด 20 แท่ง แท่งแรกแดง แท่งสองเขียว → Tweezer Bottom BUY; กลับด้าน Tweezer Top SELL', 'sl_atr': 1.2, 'rr': 1.5, 'max_hold': 20}


def generate(df, tf):
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    a = I.atr(df, 14)
    tb = ((l - l.shift(1)).abs() <= 0.05 * a) & (c.shift(1) < o.shift(1)) & (c > o) & (pd.concat([l, l.shift(1)], axis=1).min(axis=1) <= I.lowest(l, 20))
    tt = ((h - h.shift(1)).abs() <= 0.05 * a) & (c.shift(1) > o.shift(1)) & (c < o) & (pd.concat([h, h.shift(1)], axis=1).max(axis=1) >= I.highest(h, 20))
    return I.sig_from(tb, tt)
