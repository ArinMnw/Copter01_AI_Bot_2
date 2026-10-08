# -*- coding: utf-8 -*-
"""S20.298 — Chaikin Volatility Spike Reversal

แนวคิด: Chaikin Volatility = ROC10 ของ EMA10(high−low): พุ่งเกิน +50% (ตื่นตระหนก) แล้วเริ่มลดลง พร้อมแท่งกลับทิศเทียบ 5 แท่งก่อน → เข้าสวนทิศที่วิ่งมา
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.298', 'name': 'Chaikin Volatility Spike Reversal', 'concept': 'Chaikin Volatility = ROC10 ของ EMA10(high−low): พุ่งเกิน +50% (ตื่นตระหนก) แล้วเริ่มลดลง พร้อมแท่งกลับทิศเทียบ 5 แท่งก่อน → เข้าสวนทิศที่วิ่งมา', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 16}


def generate(df, tf):
    o, c = df["open"], df["close"]
    ev = I.ema(df["high"] - df["low"], 10)
    cv = 100 * (ev / ev.shift(10) - 1)
    spike = (cv.shift(1) > 50) & (cv < cv.shift(1))
    return I.sig_from(spike & (c.shift(1) < c.shift(6)) & (c > o), spike & (c.shift(1) > c.shift(6)) & (c < o))
