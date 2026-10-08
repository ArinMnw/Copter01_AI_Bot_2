# -*- coding: utf-8 -*-
"""S20.250 — Raschke 'Anti' Stochastic Hook

แนวคิด: Linda Raschke Anti: Stochastic %D ช้า (7,10) ชันขึ้น (trend) %K เร็วย่อลงแล้วหักหัวกลับขึ้น (hook) ในทิศ %D → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.250', 'name': "Raschke 'Anti' Stochastic Hook", 'concept': 'Linda Raschke Anti: Stochastic %D ช้า (7,10) ชันขึ้น (trend) %K เร็วย่อลงแล้วหักหัวกลับขึ้น (hook) ในทิศ %D → BUY; กลับด้าน → SELL', 'sl_atr': 1.2, 'rr': 1.5, 'max_hold': 16}


def generate(df, tf):
    k, d = I.stoch(df, 7, 1, 10)
    up = d > d.shift(1); dn = d < d.shift(1)
    hook_up = (k.shift(1) < k.shift(2)) & (k > k.shift(1)) & (k.shift(1) > 30)
    hook_dn = (k.shift(1) > k.shift(2)) & (k < k.shift(1)) & (k.shift(1) < 70)
    return I.sig_from(up & hook_up, dn & hook_dn)
