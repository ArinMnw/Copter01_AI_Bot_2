# -*- coding: utf-8 -*-
"""S20.214 — MACD Histogram Trough Hook Below Zero

แนวคิด: MACD histogram ใต้ศูนย์ทำก้น (ลดลง 3 แท่งแล้วเพิ่มขึ้น) ขณะ MACD line ยังใต้ศูนย์ลึก (< −0.5 ATR) → BUY ช่วงต้นการกลับตัว; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.214', 'name': 'MACD Histogram Trough Hook Below Zero', 'concept': 'MACD histogram ใต้ศูนย์ทำก้น (ลดลง 3 แท่งแล้วเพิ่มขึ้น) ขณะ MACD line ยังใต้ศูนย์ลึก (< −0.5 ATR) → BUY ช่วงต้นการกลับตัว; กลับด้าน → SELL', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 20}


def generate(df, tf):
    m, _, hs = I.macd(df["close"])
    a = I.atr(df, 14)
    d = hs.diff()
    tr_b = (hs < 0) & (d.shift(1) < 0) & (d.shift(2) < 0) & (d.shift(3) < 0) & (d > 0) & (m < -0.5 * a)
    tr_s = (hs > 0) & (d.shift(1) > 0) & (d.shift(2) > 0) & (d.shift(3) > 0) & (d < 0) & (m > 0.5 * a)
    return I.sig_from(tr_b, tr_s)
