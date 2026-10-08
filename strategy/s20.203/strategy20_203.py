# -*- coding: utf-8 -*-
"""S20.203 — Golden/Death Cross SMA50-200

แนวคิด: SMA50 ตัดขึ้นเหนือ SMA200 (Golden Cross) → BUY; ตัดลง (Death Cross) → SELL — trend สัญญาณคลาสสิกระยะยาว ถือนาน
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.203', 'name': 'Golden/Death Cross SMA50-200', 'concept': 'SMA50 ตัดขึ้นเหนือ SMA200 (Golden Cross) → BUY; ตัดลง (Death Cross) → SELL — trend สัญญาณคลาสสิกระยะยาว ถือนาน', 'sl_atr': 2.5, 'rr': 2.0, 'max_hold': 80}


def generate(df, tf):
    s50, s200 = I.sma(df["close"], 50), I.sma(df["close"], 200)
    return I.sig_from(I.cross_up(s50, s200), I.cross_dn(s50, s200))
