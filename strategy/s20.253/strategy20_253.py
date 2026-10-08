# -*- coding: utf-8 -*-
"""S20.253 — Larry Williams Oops Reversal

แนวคิด: Larry Williams Oops: งวดใหม่เปิดต่ำกว่า low ของงวดก่อน (gap ลง/ขายตกใจ) แล้วราคาปิดกลับขึ้นเหนือ low งวดก่อน → BUY; เปิดเหนือ high งวดก่อนแล้วหลุดกลับใต้ → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.253', 'name': 'Larry Williams Oops Reversal', 'concept': 'Larry Williams Oops: งวดใหม่เปิดต่ำกว่า low ของงวดก่อน (gap ลง/ขายตกใจ) แล้วราคาปิดกลับขึ้นเหนือ low งวดก่อน → BUY; เปิดเหนือ high งวดก่อนแล้วหลุดกลับใต้ → SELL', 'sl_atr': 1.2, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    key = I.period_key(df, tf) if tf != "D1" else I.day_key(df)
    ph, pl, _, _ = I.prev_period_hl(df, key)
    _, _, po = I.period_running(df, key)
    c = df["close"]
    if tf == "D1":
        po = df["open"]; ph = df["high"].shift(1); pl = df["low"].shift(1)
    b = (po < pl) & (c > pl); s = (po > ph) & (c < ph)
    if tf != "D1":
        b = b & (b.astype(int).groupby(key).cumsum() == 1); s = s & (s.astype(int).groupby(key).cumsum() == 1)
    return I.sig_from(b, s)
