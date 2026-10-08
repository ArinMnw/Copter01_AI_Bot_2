# -*- coding: utf-8 -*-
"""S20.159 — TRIX Signal-Line Cross in Trend

แนวคิด: TRIX(15) (ROC ของ EMA 3 ชั้น) ตัด signal EMA9 ขึ้นขณะ TRIX<0 (ต้น cycle) และ close > EMA100 → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.159', 'name': 'TRIX Signal-Line Cross in Trend', 'concept': 'TRIX(15) (ROC ของ EMA 3 ชั้น) ตัด signal EMA9 ขึ้นขณะ TRIX<0 (ต้น cycle) และ close > EMA100 → BUY; กลับด้าน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    e = I.ema(I.ema(I.ema(df["close"], 15), 15), 15)
    trix = 10000 * e.pct_change()
    sg = I.ema(trix, 9)
    e100 = I.ema(df["close"], 100)
    return I.sig_from(I.cross_up(trix, sg) & (trix < 0) & (df["close"] > e100),
                      I.cross_dn(trix, sg) & (trix > 0) & (df["close"] < e100))
