# -*- coding: utf-8 -*-
"""S20.293 — Two-Legged ABC Pullback to EMA20

แนวคิด: Trend ขึ้น (EMA20 > EMA50) ราคาย่อเป็น 2 ขา (low ย่อย 2 จุดต่ำลงตามลำดับ ผ่าน confirmed pivot 1/1) ลงมาใกล้ EMA20 (< 0.5 ATR) แล้วปิดเหนือ high แท่งก่อน → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.293', 'name': 'Two-Legged ABC Pullback to EMA20', 'concept': 'Trend ขึ้น (EMA20 > EMA50) ราคาย่อเป็น 2 ขา (low ย่อย 2 จุดต่ำลงตามลำดับ ผ่าน confirmed pivot 1/1) ลงมาใกล้ EMA20 (< 0.5 ATR) แล้วปิดเหนือ high แท่งก่อน → BUY; กลับด้าน → SELL', 'sl_atr': 1.2, 'rr': 2.0, 'max_hold': 20}


def generate(df, tf):
    c, h, l = df["close"], df["high"], df["low"]
    e20, e50 = I.ema(c, 20), I.ema(c, 50)
    a = I.atr(df, 14)
    pl = I.confirmed_pivot_low(df, 1, 1); ph = I.confirmed_pivot_high(df, 1, 1)
    pl_last = pl.ffill(); pl_prev = pl.dropna().shift(1).reindex(df.index).ffill()
    ph_last = ph.ffill(); ph_prev = ph.dropna().shift(1).reindex(df.index).ffill()
    two_dn = pl_last < pl_prev; two_up = ph_last > ph_prev
    near_b = (l.rolling(3).min() - e20).abs() < 0.5 * a
    near_s = (h.rolling(3).max() - e20).abs() < 0.5 * a
    return I.sig_from((e20 > e50) & two_dn & near_b & (c > h.shift(1)), (e20 < e50) & two_up & near_s & (c < l.shift(1)))
