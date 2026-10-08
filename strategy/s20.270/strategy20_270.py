# -*- coding: utf-8 -*-
"""S20.270 — Day-Open Side EMA 9/21 Cross

แนวคิด: EMA9 ตัด EMA21 ขึ้นเฉพาะเมื่อราคาอยู่เหนือ open ของงวดใหญ่ (วันสำหรับ TF≤H1, สัปดาห์ H4, เดือน D1) = เทรดตามสีแท่ง HTF ปัจจุบัน → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.270', 'name': 'Day-Open Side EMA 9/21 Cross', 'concept': 'EMA9 ตัด EMA21 ขึ้นเฉพาะเมื่อราคาอยู่เหนือ open ของงวดใหญ่ (วันสำหรับ TF≤H1, สัปดาห์ H4, เดือน D1) = เทรดตามสีแท่ง HTF ปัจจุบัน → BUY; กลับด้าน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    key = I.period_key(df, tf)
    _, _, po = I.period_running(df, key)
    c = df["close"]
    e9, e21 = I.ema(c, 9), I.ema(c, 21)
    return I.sig_from(I.cross_up(e9, e21) & (c > po), I.cross_dn(e9, e21) & (c < po))
