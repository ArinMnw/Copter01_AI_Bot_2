# -*- coding: utf-8 -*-
"""S20.144 — Heikin-Ashi Flat-Bottom Reversal

แนวคิด: หลัง Heikin-Ashi แดง ≥3 แท่งติด เกิด HA เขียวที่ไม่มีไส้ล่าง (flat bottom = แรงซื้อเต็มแท่ง) → BUY; กลับด้าน HA แดงไม่มีไส้บน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.144', 'name': 'Heikin-Ashi Flat-Bottom Reversal', 'concept': 'หลัง Heikin-Ashi แดง ≥3 แท่งติด เกิด HA เขียวที่ไม่มีไส้ล่าง (flat bottom = แรงซื้อเต็มแท่ง) → BUY; กลับด้าน HA แดงไม่มีไส้บน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    ho, hh, hl, hc = I.heikin_ashi(df)
    bull = hc > ho
    bear = hc < ho
    tol = 0.02 * I.atr(df, 14)
    flat_bot = (pd.concat([ho, hc], axis=1).min(axis=1) - hl) <= tol
    flat_top = (hh - pd.concat([ho, hc], axis=1).max(axis=1)) <= tol
    b3 = bear.shift(1) & bear.shift(2) & bear.shift(3)
    u3 = bull.shift(1) & bull.shift(2) & bull.shift(3)
    return I.sig_from(bull & flat_bot & b3.fillna(False), bear & flat_top & u3.fillna(False))
