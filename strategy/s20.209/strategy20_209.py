# -*- coding: utf-8 -*-
"""S20.209 — STARC Band Tag Reversal

แนวคิด: Manning Stoller STARC bands (SMA6 ± 2·ATR15): แท่งทะลุ STARC บนแล้วปิดกลับใน band และปิดแดง → SELL; ทะลุล่างแล้วปิดกลับเขียว → BUY
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.209', 'name': 'STARC Band Tag Reversal', 'concept': 'Manning Stoller STARC bands (SMA6 ± 2·ATR15): แท่งทะลุ STARC บนแล้วปิดกลับใน band และปิดแดง → SELL; ทะลุล่างแล้วปิดกลับเขียว → BUY', 'sl_atr': 1.2, 'rr': 1.2, 'max_hold': 12}


def generate(df, tf):
    m = I.sma(df["close"], 6); a = I.atr(df, 15)
    up, lo = m + 2 * a, m - 2 * a
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    return I.sig_from((l < lo) & (c > lo) & (c > o), (h > up) & (c < up) & (c < o))
