# -*- coding: utf-8 -*-
"""S20.254 — Williams Smash-Day Reversal

แนวคิด: Larry Williams Smash Day: แท่งที่ปิดต่ำกว่า low ต่ำสุด 3 แท่งก่อน (smash ลง) แล้วแท่งถัดไปปิดเหนือ high ของ smash bar → BUY (กับดักคนขาย); กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.254', 'name': 'Williams Smash-Day Reversal', 'concept': 'Larry Williams Smash Day: แท่งที่ปิดต่ำกว่า low ต่ำสุด 3 แท่งก่อน (smash ลง) แล้วแท่งถัดไปปิดเหนือ high ของ smash bar → BUY (กับดักคนขาย); กลับด้าน → SELL', 'sl_atr': 1.2, 'rr': 2.0, 'max_hold': 20}


def generate(df, tf):
    h, l, c = df["high"], df["low"], df["close"]
    smash_dn = c < I.lowest(l, 3).shift(1)
    smash_up = c > I.highest(h, 3).shift(1)
    return I.sig_from(smash_dn.shift(1).fillna(False) & (c > h.shift(1)), smash_up.shift(1).fillna(False) & (c < l.shift(1)))
