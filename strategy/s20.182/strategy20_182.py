# -*- coding: utf-8 -*-
"""S20.182 — Woodie Pivot R1/S1 Close Breakout

แนวคิด: Woodie pivot (P=(H+L+2C)/4 ของงวดก่อน): ราคาปิดทะลุ R1 ขึ้นโดยเปิดงวดอยู่ใต้ R1 → BUY, ปิดหลุด S1 → SELL; ครั้งแรกของงวดเท่านั้น
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.182', 'name': 'Woodie Pivot R1/S1 Close Breakout', 'concept': 'Woodie pivot (P=(H+L+2C)/4 ของงวดก่อน): ราคาปิดทะลุ R1 ขึ้นโดยเปิดงวดอยู่ใต้ R1 → BUY, ปิดหลุด S1 → SELL; ครั้งแรกของงวดเท่านั้น', 'sl_atr': 1.2, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    key = I.period_key(df, tf)
    ph, pl, pc, _ = I.prev_period_hl(df, key)
    p = (ph + pl + 2 * pc) / 4
    r1, s1 = 2 * p - pl, 2 * p - ph
    _, _, po = I.period_running(df, key)
    c = df["close"]
    up = (c > r1) & (po < r1); dn = (c < s1) & (po > s1)
    fu = up & (up.astype(int).groupby(key).cumsum() == 1); fd = dn & (dn.astype(int).groupby(key).cumsum() == 1)
    return I.sig_from(fu, fd)
