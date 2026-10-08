# -*- coding: utf-8 -*-
"""S20.273 — ATR Acceleration Directional Thrust

แนวคิด: ATR5/ATR50 พุ่งเกิน 1.8 (volatility เร่งตัวกระทันหัน) พร้อม close ห่าง EMA10 > 1 ATR50 → เข้าตามทิศของแรงผลัก (ไม่ใช่ fade)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.273', 'name': 'ATR Acceleration Directional Thrust', 'concept': 'ATR5/ATR50 พุ่งเกิน 1.8 (volatility เร่งตัวกระทันหัน) พร้อม close ห่าง EMA10 > 1 ATR50 → เข้าตามทิศของแรงผลัก (ไม่ใช่ fade)', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 16}


def generate(df, tf):
    a5, a50 = I.atr(df, 5), I.atr(df, 50)
    acc = a5 / a50
    e10 = I.ema(df["close"], 10)
    th = I.cross_up(acc, 1.8)
    return I.sig_from(th & (df["close"] - e10 > a50), th & (e10 - df["close"] > a50))
