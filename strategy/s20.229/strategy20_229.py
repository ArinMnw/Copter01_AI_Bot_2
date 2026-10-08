# -*- coding: utf-8 -*-
"""S20.229 — Volume-Confirmed Donchian-20 Breakout

แนวคิด: ปิดทะลุ Donchian 20 แท่ง พร้อม tick volume > 2 เท่าค่าเฉลี่ย 50 แท่ง (breakout ที่มีคนร่วมจริง) → เข้าตามทิศ
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.229', 'name': 'Volume-Confirmed Donchian-20 Breakout', 'concept': 'ปิดทะลุ Donchian 20 แท่ง พร้อม tick volume > 2 เท่าค่าเฉลี่ย 50 แท่ง (breakout ที่มีคนร่วมจริง) → เข้าตามทิศ', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    c, v = df["close"], df["volume"]
    hh, ll = I.highest(df["high"], 20).shift(1), I.lowest(df["low"], 20).shift(1)
    vol = v > 2 * I.sma(v, 50).shift(1)
    return I.sig_from((c > hh) & vol, (c < ll) & vol)
