# -*- coding: utf-8 -*-
"""S20.267 — Monday Continuation of Prior-Week Direction

แนวคิด: ถ้าสัปดาห์ก่อนปิดใกล้ high (close อยู่ใน 25% บนของ range สัปดาห์) → BUY ที่แท่งแรกหลัง 07:00 UTC วันจันทร์ ถ้าราคายังอยู่เหนือ close สัปดาห์ก่อน; ใกล้ low → SELL (TF ≤ H4)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.267', 'name': 'Monday Continuation of Prior-Week Direction', 'concept': 'ถ้าสัปดาห์ก่อนปิดใกล้ high (close อยู่ใน 25% บนของ range สัปดาห์) → BUY ที่แท่งแรกหลัง 07:00 UTC วันจันทร์ ถ้าราคายังอยู่เหนือ close สัปดาห์ก่อน; ใกล้ low → SELL (TF ≤ H4)', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    if tf == "D1":
        return np.zeros(len(df), dtype=np.int8)
    wk = I.week_key(df)
    ph, pl, pc, _ = I.prev_period_hl(df, wk)
    pos = (pc - pl) / (ph - pl).replace(0, np.nan)
    hr = I.hour(df); dw = I.dow(df)
    first = (dw == 0) & (hr >= 7) & ~((dw.shift(1) == 0) & (hr.shift(1) >= 7))
    c = df["close"]
    return I.sig_from(first & (pos > 0.75) & (c > pc), first & (pos < 0.25) & (c < pc))
