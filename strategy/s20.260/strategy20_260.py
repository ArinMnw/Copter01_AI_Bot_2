# -*- coding: utf-8 -*-
"""S20.260 — Kicker Pattern Momentum Flip

แนวคิด: Kicker: แท่งแดงเนื้อยาวตามด้วยแท่งเขียวที่เปิดเหนือ open ของแท่งแดง (กระโดดข้าม) และปิดเขียวยาว → BUY ทันที; กลับด้าน → SELL (sentiment เปลี่ยนแบบฉับพลัน)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.260', 'name': 'Kicker Pattern Momentum Flip', 'concept': 'Kicker: แท่งแดงเนื้อยาวตามด้วยแท่งเขียวที่เปิดเหนือ open ของแท่งแดง (กระโดดข้าม) และปิดเขียวยาว → BUY ทันที; กลับด้าน → SELL (sentiment เปลี่ยนแบบฉับพลัน)', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 16}


def generate(df, tf):
    o, c = df["open"], df["close"]
    a = I.atr(df, 14)
    k_up = (c.shift(1) < o.shift(1)) & ((o.shift(1) - c.shift(1)) > 0.6 * a) & (o >= o.shift(1)) & ((c - o) > 0.6 * a)
    k_dn = (c.shift(1) > o.shift(1)) & ((c.shift(1) - o.shift(1)) > 0.6 * a) & (o <= o.shift(1)) & ((o - c) > 0.6 * a)
    return I.sig_from(k_up, k_dn)
