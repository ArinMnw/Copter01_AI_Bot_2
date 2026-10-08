# -*- coding: utf-8 -*-
"""S20.180 — Wide-Range Marubozu Continuation

แนวคิด: แท่ง Wide-Range (range > 2×ATR14 ก่อนหน้า) แบบ marubozu (body ≥ 80% ของ range) = แรงสถาบันทางเดียว → เข้าตามทิศแท่งนั้นทันทีแท่งถัดไป
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.180', 'name': 'Wide-Range Marubozu Continuation', 'concept': 'แท่ง Wide-Range (range > 2×ATR14 ก่อนหน้า) แบบ marubozu (body ≥ 80% ของ range) = แรงสถาบันทางเดียว → เข้าตามทิศแท่งนั้นทันทีแท่งถัดไป', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 16}


def generate(df, tf):
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    rg = h - l
    a = I.atr(df, 14).shift(1)
    wrb = (rg > 2 * a) & ((c - o).abs() >= 0.8 * rg)
    return I.sig_from(wrb & (c > o), wrb & (c < o))
