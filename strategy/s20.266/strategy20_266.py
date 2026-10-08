# -*- coding: utf-8 -*-
"""S20.266 — Friday Afternoon Weekly Profit-Taking Fade

แนวคิด: ถ้าสัปดาห์นี้ (open วันจันทร์ → บ่ายศุกร์ 15 UTC) วิ่งเกิน 2% ให้เข้าสวนทิศที่แท่งแรกหลัง 15:00 UTC วันศุกร์ (ปิดสถานะก่อนสุดสัปดาห์) — TF ≤ H1
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.266', 'name': 'Friday Afternoon Weekly Profit-Taking Fade', 'concept': 'ถ้าสัปดาห์นี้ (open วันจันทร์ → บ่ายศุกร์ 15 UTC) วิ่งเกิน 2% ให้เข้าสวนทิศที่แท่งแรกหลัง 15:00 UTC วันศุกร์ (ปิดสถานะก่อนสุดสัปดาห์) — TF ≤ H1', 'sl_atr': 1.5, 'rr': 1.0, 'max_hold': 1, 'max_hold_tf': {'M1': 300, 'M5': 60, 'M15': 20, 'M30': 10, 'H1': 5}}


def generate(df, tf):
    if tf in ("H4", "D1"):
        return np.zeros(len(df), dtype=np.int8)
    wk = I.week_key(df); _, _, wo = I.period_running(df, wk)
    hr = I.hour(df); dw = I.dow(df)
    tfs = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600}[tf]
    edge = (dw == 4) & (hr == 14) & (((df["time"] + tfs) % 86400) // 3600 == 15)
    mv = df["close"] / wo - 1
    return I.sig_from(edge & (mv < -0.02), edge & (mv > 0.02))
