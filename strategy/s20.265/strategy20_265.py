# -*- coding: utf-8 -*-
"""S20.265 — NY Lunch Trend Reversal

แนวคิด: ทิศช่วง NY เช้า (13–16 UTC) ที่วิ่งเกิน 2 ATR มักถูก take-profit ช่วงพักเที่ยง NY: ที่แท่งแรกหลัง 16:00 UTC เข้าสวนทิศนั้น (TF ≤ H1)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.265', 'name': 'NY Lunch Trend Reversal', 'concept': 'ทิศช่วง NY เช้า (13–16 UTC) ที่วิ่งเกิน 2 ATR มักถูก take-profit ช่วงพักเที่ยง NY: ที่แท่งแรกหลัง 16:00 UTC เข้าสวนทิศนั้น (TF ≤ H1)', 'sl_atr': 1.2, 'rr': 1.2, 'max_hold': 12}


def generate(df, tf):
    if tf in ("H4", "D1"):
        return np.zeros(len(df), dtype=np.int8)
    t = df["time"]; hr = I.hour(df); day = I.day_key(df)
    o13 = df["open"].where(hr == 13).groupby(day).transform("first")
    c = df["close"]
    nxt_hr = ((t + {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600}[tf]) % 86400) // 3600
    edge = (hr == 15) & (nxt_hr == 16)
    mv = c - o13
    a = I.atr(df, 14)
    return I.sig_from(edge & (mv < -2 * a), edge & (mv > 2 * a))
