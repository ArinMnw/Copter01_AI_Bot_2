# -*- coding: utf-8 -*-
"""S20.150 — Camarilla H3/L3 Fade

แนวคิด: Camarilla pivot จาก HLC ของงวดก่อน: แท่งแตะ H3 แล้วปิดกลับใต้ H3 → SELL, แตะ L3 แล้วปิดกลับเหนือ L3 → BUY (ไม่เทรดถ้าเปิดงวดนอก H4/L4)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.150', 'name': 'Camarilla H3/L3 Fade', 'concept': 'Camarilla pivot จาก HLC ของงวดก่อน: แท่งแตะ H3 แล้วปิดกลับใต้ H3 → SELL, แตะ L3 แล้วปิดกลับเหนือ L3 → BUY (ไม่เทรดถ้าเปิดงวดนอก H4/L4)', 'sl_atr': 1.0, 'rr': 1.5, 'max_hold': 16}


def generate(df, tf):
    key = I.period_key(df, tf)
    ph, pl, pc, _ = I.prev_period_hl(df, key)
    rg = ph - pl
    h3, l3 = pc + rg * 1.1 / 4, pc - rg * 1.1 / 4
    h4, l4 = pc + rg * 1.1 / 2, pc - rg * 1.1 / 2
    _, _, po = I.period_running(df, key)
    inside = (po < h4) & (po > l4)
    return I.sig_from(inside & (df["low"] <= l3) & (df["close"] > l3) & (df["close"].shift(1) > l3),
                      inside & (df["high"] >= h3) & (df["close"] < h3) & (df["close"].shift(1) < h3))
