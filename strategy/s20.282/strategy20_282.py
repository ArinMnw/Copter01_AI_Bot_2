# -*- coding: utf-8 -*-
"""S20.282 — Tillson T3 Slope Flip

แนวคิด: Tim Tillson T3 (5, vfactor 0.7) — 6-fold EMA ที่เรียบและ lag ต่ำ: T3 เปลี่ยนทิศ (slope flip เกิน 0.03 ATR) ตามทิศ T3(20) → เข้าไม้
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.282', 'name': 'Tillson T3 Slope Flip', 'concept': 'Tim Tillson T3 (5, vfactor 0.7) — 6-fold EMA ที่เรียบและ lag ต่ำ: T3 เปลี่ยนทิศ (slope flip เกิน 0.03 ATR) ตามทิศ T3(20) → เข้าไม้', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    def t3(x, n, v=0.7):
        e1 = I.ema(x, n); e2 = I.ema(e1, n); e3 = I.ema(e2, n); e4 = I.ema(e3, n); e5 = I.ema(e4, n); e6 = I.ema(e5, n)
        c1 = -v ** 3; c2 = 3 * v * v + 3 * v ** 3; c3 = -6 * v * v - 3 * v - 3 * v ** 3; c4 = 1 + 3 * v + v ** 3 + 3 * v * v
        return c1 * e6 + c2 * e5 + c3 * e4 + c4 * e3
    f, s = t3(df["close"], 5), t3(df["close"], 20)
    d = f.diff(); a = I.atr(df, 14)
    return I.sig_from((d > 0.03 * a) & (d.shift(1) <= 0) & (s.diff() > 0), (d < -0.03 * a) & (d.shift(1) >= 0) & (s.diff() < 0))
