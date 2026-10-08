# -*- coding: utf-8 -*-
"""S20.208 — ADX Rising Out of Dormancy

แนวคิด: ADX14 ต่ำกว่า 20 อย่างน้อย 10 แท่ง (ไม่มี trend) แล้วตัดขึ้นเหนือ 20 → trend ใหม่ เข้าตามทิศ DI ที่นำ
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.208', 'name': 'ADX Rising Out of Dormancy', 'concept': 'ADX14 ต่ำกว่า 20 อย่างน้อย 10 แท่ง (ไม่มี trend) แล้วตัดขึ้นเหนือ 20 → trend ใหม่ เข้าตามทิศ DI ที่นำ', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    pdi, ndi, adx = I.dmi(df, 14)
    dorm = (adx.shift(1) < 20).rolling(10).sum() == 10
    on = I.cross_up(adx, 20) & dorm
    return I.sig_from(on & (pdi > ndi), on & (ndi > pdi))
