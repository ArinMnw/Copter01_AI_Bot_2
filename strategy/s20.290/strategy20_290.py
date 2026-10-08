# -*- coding: utf-8 -*-
"""S20.290 — WaveTrend Oscillator Cross

แนวคิด: WaveTrend (LazyBear, 10/21): wt1 ตัด wt2 ขึ้นใน oversold (< −53) → BUY; ตัดลงใน overbought (> 53) → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.290', 'name': 'WaveTrend Oscillator Cross', 'concept': 'WaveTrend (LazyBear, 10/21): wt1 ตัด wt2 ขึ้นใน oversold (< −53) → BUY; ตัดลงใน overbought (> 53) → SELL', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 20}


def generate(df, tf):
    ap = (df["high"] + df["low"] + df["close"]) / 3
    esa = I.ema(ap, 10); d = I.ema((ap - esa).abs(), 10)
    ci = (ap - esa) / (0.015 * d.replace(0, np.nan))
    wt1 = I.ema(ci, 21); wt2 = I.sma(wt1, 4)
    return I.sig_from(I.cross_up(wt1, wt2) & (wt1 < -53), I.cross_dn(wt1, wt2) & (wt1 > 53))
