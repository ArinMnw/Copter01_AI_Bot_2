# -*- coding: utf-8 -*-
"""S20.207 — Bollinger %B Expansion Breakout

แนวคิด: John Bollinger: %B > 1 (ปิดนอกแถบบน) พร้อม BandWidth ขยาย > 1.5 เท่าของ BandWidth ต่ำสุด 50 แท่ง = volatility breakout → BUY; %B < 0 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.207', 'name': 'Bollinger %B Expansion Breakout', 'concept': 'John Bollinger: %B > 1 (ปิดนอกแถบบน) พร้อม BandWidth ขยาย > 1.5 เท่าของ BandWidth ต่ำสุด 50 แท่ง = volatility breakout → BUY; %B < 0 → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    bl, bm, bu = I.bbands(df["close"], 20, 2.0)
    pb = (df["close"] - bl) / (bu - bl).replace(0, np.nan)
    bw = (bu - bl) / bm
    exp = bw > 1.5 * bw.rolling(50).min()
    return I.sig_from((pb > 1) & (pb.shift(1) <= 1) & exp, (pb < 0) & (pb.shift(1) >= 0) & exp)
