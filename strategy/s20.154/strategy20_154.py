# -*- coding: utf-8 -*-
"""S20.154 — Aroon Trend Ignition

แนวคิด: Aroon(25): Aroon-Up ตัดขึ้นเหนือ Aroon-Down และ Aroon-Up ≥ 70 (เพิ่งทำ high ใหม่เร็วๆ) ขณะ Aroon-Down ≤ 30 → BUY; สลับ → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.154', 'name': 'Aroon Trend Ignition', 'concept': 'Aroon(25): Aroon-Up ตัดขึ้นเหนือ Aroon-Down และ Aroon-Up ≥ 70 (เพิ่งทำ high ใหม่เร็วๆ) ขณะ Aroon-Down ≤ 30 → BUY; สลับ → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 40}


def generate(df, tf):
    n = 25
    au = 100 * df["high"].rolling(n + 1).apply(lambda x: x.argmax(), raw=True) / n
    ad = 100 * df["low"].rolling(n + 1).apply(lambda x: x.argmin(), raw=True) / n
    buy = I.cross_up(au, ad) & (au >= 70) & (ad <= 30)
    sell = I.cross_up(ad, au) & (ad >= 70) & (au <= 30)
    return I.sig_from(buy, sell)
