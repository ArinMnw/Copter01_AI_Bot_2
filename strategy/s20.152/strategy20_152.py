# -*- coding: utf-8 -*-
"""S20.152 — Bill Williams Fractal Breakout beyond Alligator Teeth

แนวคิด: Fractal (5 แท่ง ยืนยันแล้ว 2 แท่งขวา) ที่อยู่นอกปาก Alligator: ราคาปิดทะลุ up-fractal ล่าสุดที่อยู่เหนือ Teeth → BUY; ทะลุ down-fractal ใต้ Teeth → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.152', 'name': 'Bill Williams Fractal Breakout beyond Alligator Teeth', 'concept': 'Fractal (5 แท่ง ยืนยันแล้ว 2 แท่งขวา) ที่อยู่นอกปาก Alligator: ราคาปิดทะลุ up-fractal ล่าสุดที่อยู่เหนือ Teeth → BUY; ทะลุ down-fractal ใต้ Teeth → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    med = (df["high"] + df["low"]) / 2
    teeth = I.rma(med, 8).shift(5)
    fu = I.confirmed_pivot_high(df, 2, 2).ffill()
    fd = I.confirmed_pivot_low(df, 2, 2).ffill()
    c = df["close"]
    buy = (c > fu) & (c.shift(1) <= fu.shift(1)) & (fu > teeth)
    sell = (c < fd) & (c.shift(1) >= fd.shift(1)) & (fd < teeth)
    return I.sig_from(buy, sell)
