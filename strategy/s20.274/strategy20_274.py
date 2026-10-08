# -*- coding: utf-8 -*-
"""S20.274 — Donchian Midline Cross with 55-Channel Bias

แนวคิด: ราคาปิดตัดขึ้นเหนือเส้นกลาง Donchian 20 ขณะเส้นกลาง Donchian 55 ชันขึ้น (bias ใหญ่) → BUY; ตัดลง + mid55 ลง → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.274', 'name': 'Donchian Midline Cross with 55-Channel Bias', 'concept': 'ราคาปิดตัดขึ้นเหนือเส้นกลาง Donchian 20 ขณะเส้นกลาง Donchian 55 ชันขึ้น (bias ใหญ่) → BUY; ตัดลง + mid55 ลง → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    h, l, c = df["high"], df["low"], df["close"]
    m20 = (I.highest(h, 20) + I.lowest(l, 20)) / 2
    m55 = (I.highest(h, 55) + I.lowest(l, 55)) / 2
    return I.sig_from(I.cross_up(c, m20) & (m55 > m55.shift(5)), I.cross_dn(c, m20) & (m55 < m55.shift(5)))
