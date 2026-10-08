# -*- coding: utf-8 -*-
"""S20.264 — Asian-Range Midpoint Magnet

แนวคิด: หลังจบ Asia (00–07 UTC) ถ้าราคาช่วง London/NY ปิดห่าง midpoint ของ Asian range > 1.5 ATR แล้วแท่งปิดสวนกลับ → เข้าสวนหา midpoint (mean-reversion รายวัน; TF ≤ H1 เท่านั้น)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.264', 'name': 'Asian-Range Midpoint Magnet', 'concept': 'หลังจบ Asia (00–07 UTC) ถ้าราคาช่วง London/NY ปิดห่าง midpoint ของ Asian range > 1.5 ATR แล้วแท่งปิดสวนกลับ → เข้าสวนหา midpoint (mean-reversion รายวัน; TF ≤ H1 เท่านั้น)', 'sl_atr': 1.2, 'rr': 1.2, 'max_hold': 12}


def generate(df, tf):
    if tf in ("H4", "D1"):
        return np.zeros(len(df), dtype=np.int8)
    hr = I.hour(df); day = I.day_key(df)
    asia = hr < 7
    ah = df["high"].where(asia).groupby(day).transform("max")
    al = df["low"].where(asia).groupby(day).transform("min")
    mid = (ah + al) / 2
    a = I.atr(df, 14)
    o, c = df["open"], df["close"]
    post = (hr >= 7) & (hr < 20)
    return I.sig_from(post & (mid - c > 1.5 * a) & (c > o), post & (c - mid > 1.5 * a) & (c < o))
