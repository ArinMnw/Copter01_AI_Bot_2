# -*- coding: utf-8 -*-
"""S20.210 — Bill Williams Accelerator Oscillator Two-Green

แนวคิด: Accelerator Oscillator (AO − SMA5 ของ AO) = ความเร่งของ momentum: AO > 0 และ AC เขียว (เพิ่มขึ้น) 2 แท่งติดหลังจากแดง → BUY; AO < 0 และ AC แดง 2 แท่งติดหลังเขียว → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.210', 'name': 'Bill Williams Accelerator Oscillator Two-Green', 'concept': 'Accelerator Oscillator (AO − SMA5 ของ AO) = ความเร่งของ momentum: AO > 0 และ AC เขียว (เพิ่มขึ้น) 2 แท่งติดหลังจากแดง → BUY; AO < 0 และ AC แดง 2 แท่งติดหลังเขียว → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    med = (df["high"] + df["low"]) / 2
    ao = I.sma(med, 5) - I.sma(med, 34)
    ac = ao - I.sma(ao, 5)
    d = ac.diff()
    g2 = (d > 0) & (d.shift(1) > 0) & (d.shift(2) <= 0)
    r2 = (d < 0) & (d.shift(1) < 0) & (d.shift(2) >= 0)
    return I.sig_from(g2 & (ao > 0) & (ac > 0), r2 & (ao < 0) & (ac < 0))
