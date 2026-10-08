# -*- coding: utf-8 -*-
"""S20.200 — Qstick Body-Pressure Zero Cross

แนวคิด: Tushar Chande Qstick(8) = SMA ของ (close−open): ตัดศูนย์ขึ้น (เนื้อเทียนเขียวครองตลาด) และ EMA50 ชันขึ้น → BUY; ตัดลง + EMA50 ลง → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.200', 'name': 'Qstick Body-Pressure Zero Cross', 'concept': 'Tushar Chande Qstick(8) = SMA ของ (close−open): ตัดศูนย์ขึ้น (เนื้อเทียนเขียวครองตลาด) และ EMA50 ชันขึ้น → BUY; ตัดลง + EMA50 ลง → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    q = I.sma(df["close"] - df["open"], 8)
    e = I.ema(df["close"], 50)
    return I.sig_from(I.cross_up(q, 0) & (e > e.shift(5)), I.cross_dn(q, 0) & (e < e.shift(5)))
