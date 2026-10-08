# -*- coding: utf-8 -*-
"""S20.153 — Awesome Oscillator Saucer

แนวคิด: Bill Williams AO saucer: AO>0 และแท่ง histogram แดง 2 แท่งติด (ย่อตัว) ตามด้วยแท่งเขียว → BUY ต่อ trend; AO<0 สลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.153', 'name': 'Awesome Oscillator Saucer', 'concept': 'Bill Williams AO saucer: AO>0 และแท่ง histogram แดง 2 แท่งติด (ย่อตัว) ตามด้วยแท่งเขียว → BUY ต่อ trend; AO<0 สลับด้าน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    med = (df["high"] + df["low"]) / 2
    ao = I.sma(med, 5) - I.sma(med, 34)
    d = ao.diff()
    buy = (ao > 0) & (ao.shift(1) > 0) & (ao.shift(2) > 0) & (d.shift(2) < 0) & (d.shift(1) < 0) & (d > 0)
    sell = (ao < 0) & (ao.shift(1) < 0) & (ao.shift(2) < 0) & (d.shift(2) > 0) & (d.shift(1) > 0) & (d < 0)
    return I.sig_from(buy, sell)
