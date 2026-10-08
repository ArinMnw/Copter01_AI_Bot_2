# -*- coding: utf-8 -*-
"""S20.231 — Three-Line Break Reversal

แนวคิด: Three-Line Break chart แบบ causal: เส้นใหม่เกิดเมื่อ close ทำ high/low ใหม่เหนือเส้นล่าสุด; กลับทิศได้เมื่อ close ทะลุ extreme ของ 3 เส้นล่าสุด → เข้าตามทิศที่กลับ
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.231', 'name': 'Three-Line Break Reversal', 'concept': 'Three-Line Break chart แบบ causal: เส้นใหม่เกิดเมื่อ close ทำ high/low ใหม่เหนือเส้นล่าสุด; กลับทิศได้เมื่อ close ทะลุ extreme ของ 3 เส้นล่าสุด → เข้าตามทิศที่กลับ', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    c = df["close"].to_numpy()
    n = len(c); sig = np.zeros(n, dtype=np.int8)
    lines = []  # (low, high, dir)
    for i in range(1, n):
        if not lines:
            if c[i] != c[0]:
                lines.append((min(c[0], c[i]), max(c[0], c[i]), 1 if c[i] > c[0] else -1))
            continue
        lo, hi, d = lines[-1]
        last3 = lines[-3:]
        if d == 1:
            if c[i] > hi:
                lines.append((hi, c[i], 1))
            elif c[i] < min(x[0] for x in last3):
                lines.append((c[i], lo, -1)); sig[i] = -1
        else:
            if c[i] < lo:
                lines.append((c[i], lo, -1))
            elif c[i] > max(x[1] for x in last3):
                lines.append((hi, c[i], 1)); sig[i] = 1
        lines = lines[-5:]
    return sig
