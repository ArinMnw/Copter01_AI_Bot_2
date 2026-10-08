# -*- coding: utf-8 -*-
"""S20.212 — Ichimoku TK Cross Above Cloud with Chikou Clear

แนวคิด: Tenkan ตัดขึ้น Kijun ขณะราคาอยู่เหนือ Kumo และ Chikou (close ปัจจุบัน) สูงกว่า high ของ 26 แท่งก่อน → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.212', 'name': 'Ichimoku TK Cross Above Cloud with Chikou Clear', 'concept': 'Tenkan ตัดขึ้น Kijun ขณะราคาอยู่เหนือ Kumo และ Chikou (close ปัจจุบัน) สูงกว่า high ของ 26 แท่งก่อน → BUY; กลับด้าน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 40}


def generate(df, tf):
    h, l, c = df["high"], df["low"], df["close"]
    ten = (I.highest(h, 9) + I.lowest(l, 9)) / 2
    kij = (I.highest(h, 26) + I.lowest(l, 26)) / 2
    sa = ((ten + kij) / 2).shift(26)
    sb = ((I.highest(h, 52) + I.lowest(l, 52)) / 2).shift(26)
    top, bot = np.maximum(sa, sb), np.minimum(sa, sb)
    return I.sig_from(I.cross_up(ten, kij) & (c > top) & (c > h.shift(26)), I.cross_dn(ten, kij) & (c < bot) & (c < l.shift(26)))
