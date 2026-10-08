# -*- coding: utf-8 -*-
"""S20.194 — Chande Kroll Stop Flip

แนวคิด: Chande Kroll Stop (p=10, x=1, q=9): ราคาปิดทะลุ stop-short line ขึ้น (ทั้งสองเส้นอยู่ใต้ราคา) → BUY; ปิดหลุด stop-long line → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.194', 'name': 'Chande Kroll Stop Flip', 'concept': 'Chande Kroll Stop (p=10, x=1, q=9): ราคาปิดทะลุ stop-short line ขึ้น (ทั้งสองเส้นอยู่ใต้ราคา) → BUY; ปิดหลุด stop-long line → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    a = I.atr(df, 10)
    fh = I.highest(df["high"], 10) - a; fl = I.lowest(df["low"], 10) + a
    stop_long = I.highest(fh, 9); stop_short = I.lowest(fl, 9)
    c = df["close"]
    bull = (c > stop_short) & (c > stop_long); bear = (c < stop_long) & (c < stop_short)
    return I.sig_from(bull & ~bull.shift(1).fillna(False), bear & ~bear.shift(1).fillna(False))
