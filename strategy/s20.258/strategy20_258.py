# -*- coding: utf-8 -*-
"""S20.258 — Belt-Hold Opening Marubozu at Extreme

แนวคิด: Belt-hold: แท่งเปิดที่ low ของตัวเอง (ไส้ล่าง < 5% range) ปิดเขียวยาว > 1 ATR ขณะเปิดใต้ low ต่ำสุด 10 แท่ง → BUY; bearish belt-hold ที่ high 10 แท่ง → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.258', 'name': 'Belt-Hold Opening Marubozu at Extreme', 'concept': 'Belt-hold: แท่งเปิดที่ low ของตัวเอง (ไส้ล่าง < 5% range) ปิดเขียวยาว > 1 ATR ขณะเปิดใต้ low ต่ำสุด 10 แท่ง → BUY; bearish belt-hold ที่ high 10 แท่ง → SELL', 'sl_atr': 1.2, 'rr': 1.5, 'max_hold': 16}


def generate(df, tf):
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    a = I.atr(df, 14); rg = (h - l).replace(0, np.nan)
    bb = ((o - l) / rg < 0.05) & ((c - o) > a) & (o <= I.lowest(l, 10).shift(1))
    sb = ((h - o) / rg < 0.05) & ((o - c) > a) & (o >= I.highest(h, 10).shift(1))
    return I.sig_from(bb, sb)
