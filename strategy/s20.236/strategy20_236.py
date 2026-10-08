# -*- coding: utf-8 -*-
"""S20.236 — Bull/Bear Flag after Impulse Pole

แนวคิด: Pole = ขึ้น ≥ 3 ATR ใน 8 แท่ง, Flag = 4–10 แท่งถัดมาย่อไม่เกิน 50% ของ pole และ range แคบ; ราคาปิดทะลุ high ของ flag → BUY; bear flag กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.236', 'name': 'Bull/Bear Flag after Impulse Pole', 'concept': 'Pole = ขึ้น ≥ 3 ATR ใน 8 แท่ง, Flag = 4–10 แท่งถัดมาย่อไม่เกิน 50% ของ pole และ range แคบ; ราคาปิดทะลุ high ของ flag → BUY; bear flag กลับด้าน → SELL', 'sl_atr': 1.2, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    h, l, c = df["high"], df["low"], df["close"]
    a = I.atr(df, 14)
    fl = 6
    pole_up = (c.shift(fl) - c.shift(fl + 8)) >= 3 * a.shift(fl)
    pole_dn = (c.shift(fl + 8) - c.shift(fl)) >= 3 * a.shift(fl)
    fh = h.shift(1).rolling(fl).max(); flo = l.shift(1).rolling(fl).min()
    pole = (c.shift(fl) - c.shift(fl + 8)).abs()
    tight = (fh - flo) < 0.6 * pole
    bull = pole_up & tight & (c.shift(fl) - flo <= 0.5 * pole) & (c > fh)
    bear = pole_dn & tight & (fh - c.shift(fl) <= 0.5 * pole) & (c < flo)
    return I.sig_from(bull, bear)
