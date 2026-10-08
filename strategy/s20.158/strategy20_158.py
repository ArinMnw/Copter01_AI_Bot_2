# -*- coding: utf-8 -*-
"""S20.158 — Hull MA Turning Point with HMA-100 Bias

แนวคิด: Hull MA(21) เปลี่ยนทิศ (จุดวกกลับ) ในทิศเดียวกับ Hull MA(100) ที่เป็น bias ใหญ่ → เข้าตาม bias เมื่อ HMA สั้นกลับมาตามทิศ
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.158', 'name': 'Hull MA Turning Point with HMA-100 Bias', 'concept': 'Hull MA(21) เปลี่ยนทิศ (จุดวกกลับ) ในทิศเดียวกับ Hull MA(100) ที่เป็น bias ใหญ่ → เข้าตาม bias เมื่อ HMA สั้นกลับมาตามทิศ', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    h21 = I.hma(df["close"], 21)
    h100 = I.hma(df["close"], 100)
    d = h21.diff(); db = h100.diff()
    return I.sig_from((d > 0) & (d.shift(1) <= 0) & (db > 0), (d < 0) & (d.shift(1) >= 0) & (db < 0))
