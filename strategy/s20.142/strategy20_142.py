# -*- coding: utf-8 -*-
"""S20.142 — Parabolic SAR Flip with ADX Trend Gate

แนวคิด: Parabolic SAR (0.02/0.2) กลับทิศ และ ADX14 > 25 (มี trend จริง) + DI ฝั่งเดียวกันนำ → เข้าตามทิศ SAR ใหม่
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.142', 'name': 'Parabolic SAR Flip with ADX Trend Gate', 'concept': 'Parabolic SAR (0.02/0.2) กลับทิศ และ ADX14 > 25 (มี trend จริง) + DI ฝั่งเดียวกันนำ → เข้าตามทิศ SAR ใหม่', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 40}


def generate(df, tf):
    _, tr = I.psar(df)
    pdi, ndi, adx = I.dmi(df, 14)
    flip_up = (tr == 1) & (tr.shift(1) == -1)
    flip_dn = (tr == -1) & (tr.shift(1) == 1)
    return I.sig_from(flip_up & (adx > 25) & (pdi > ndi), flip_dn & (adx > 25) & (ndi > pdi))
