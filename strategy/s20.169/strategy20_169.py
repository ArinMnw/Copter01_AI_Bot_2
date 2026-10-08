# -*- coding: utf-8 -*-
"""S20.169 — Woodie CCI Zero-Line Reject

แนวคิด: Woodie CCI(14): trend ขึ้น (CCI > 0 อย่างน้อย 6 แท่งจาก 8) CCI ย่อลงใกล้ 0 (0..+50) แล้วดีดขึ้น → BUY ต่อ trend; ฝั่งลงกลับด้าน
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.169', 'name': 'Woodie CCI Zero-Line Reject', 'concept': 'Woodie CCI(14): trend ขึ้น (CCI > 0 อย่างน้อย 6 แท่งจาก 8) CCI ย่อลงใกล้ 0 (0..+50) แล้วดีดขึ้น → BUY ต่อ trend; ฝั่งลงกลับด้าน', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    md = tp.rolling(14).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    cci = (tp - I.sma(tp, 14)) / (0.015 * md.replace(0, np.nan))
    up = (cci.shift(1) > 0).rolling(8).sum() >= 6
    dn = (cci.shift(1) < 0).rolling(8).sum() >= 6
    buy = up & (cci.shift(1).between(0, 50)) & (cci > cci.shift(1) + 20)
    sell = dn & (cci.shift(1).between(-50, 0)) & (cci < cci.shift(1) - 20)
    return I.sig_from(buy, sell)
