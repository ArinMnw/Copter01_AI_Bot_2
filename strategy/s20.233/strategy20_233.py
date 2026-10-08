# -*- coding: utf-8 -*-
"""S20.233 — Kagi Yin-Yang Shoulder Break

แนวคิด: Kagi chart (reversal 1·ATR14) แบบ causal: เส้นกลายเป็น Yang (หนา) เมื่อราคาทะลุ shoulder (ยอดก่อนหน้า) → BUY; กลายเป็น Yin เมื่อหลุด waist (ก้นก่อนหน้า) → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.233', 'name': 'Kagi Yin-Yang Shoulder Break', 'concept': 'Kagi chart (reversal 1·ATR14) แบบ causal: เส้นกลายเป็น Yang (หนา) เมื่อราคาทะลุ shoulder (ยอดก่อนหน้า) → BUY; กลายเป็น Yin เมื่อหลุด waist (ก้นก่อนหน้า) → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    c = df["close"].to_numpy(); a = I.atr(df, 14).to_numpy()
    n = len(c); sig = np.zeros(n, dtype=np.int8)
    d = 0; ext = np.nan; shoulder = np.nan; waist = np.nan; yang = None
    for i in range(n):
        if not np.isfinite(a[i]):
            continue
        if d == 0:
            d, ext = 1, c[i]; continue
        if d == 1:
            if c[i] > ext:
                ext = c[i]
            elif c[i] < ext - a[i]:
                shoulder = ext; d, ext = -1, c[i]
        else:
            if c[i] < ext:
                ext = c[i]
            elif c[i] > ext + a[i]:
                waist = ext; d, ext = 1, c[i]
        if yang is not True and np.isfinite(shoulder) and c[i] > shoulder:
            if yang is False:
                sig[i] = 1
            yang = True
        elif yang is not False and np.isfinite(waist) and c[i] < waist:
            if yang is True:
                sig[i] = -1
            yang = False
    return sig
