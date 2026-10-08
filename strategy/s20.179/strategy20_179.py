# -*- coding: utf-8 -*-
"""S20.179 — Key Reversal Bar at 20-Bar Extreme

แนวคิด: Key Reversal: แท่งทำ low ใหม่ 20 แท่ง แต่ปิดเหนือ high ของแท่งก่อน (outside-reversal ปิดแรง) → BUY; ทำ high ใหม่ 20 แท่งแต่ปิดใต้ low แท่งก่อน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.179', 'name': 'Key Reversal Bar at 20-Bar Extreme', 'concept': 'Key Reversal: แท่งทำ low ใหม่ 20 แท่ง แต่ปิดเหนือ high ของแท่งก่อน (outside-reversal ปิดแรง) → BUY; ทำ high ใหม่ 20 แท่งแต่ปิดใต้ low แท่งก่อน → SELL', 'sl_atr': 1.2, 'rr': 2.0, 'max_hold': 20}


def generate(df, tf):
    h, l, c = df["high"], df["low"], df["close"]
    return I.sig_from((l < I.lowest(l, 20).shift(1)) & (c > h.shift(1)), (h > I.highest(h, 20).shift(1)) & (c < l.shift(1)))
