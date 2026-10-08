# -*- coding: utf-8 -*-
"""S20.185 — Turn-of-Month Gold Flow

แนวคิด: Turn-of-month effect: กระแสเงินเข้าช่วงวันทำการสุดท้ายของเดือนถึงวันที่ 3 ของเดือนใหม่ → BUY ครั้งเดียวต่อวันที่แท่งแรกหลัง 01:00 server ถ้าราคาอยู่เหนือ SMA20 ของ TF (กรอง downtrend)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.185', 'name': 'Turn-of-Month Gold Flow', 'concept': 'Turn-of-month effect: กระแสเงินเข้าช่วงวันทำการสุดท้ายของเดือนถึงวันที่ 3 ของเดือนใหม่ → BUY ครั้งเดียวต่อวันที่แท่งแรกหลัง 01:00 server ถ้าราคาอยู่เหนือ SMA20 ของ TF (กรอง downtrend)', 'sl_atr': 2.0, 'rr': 1.5, 'max_hold': 24}


def generate(df, tf):
    dt = pd.to_datetime(df["time"], unit="s")
    dom = dt.dt.day; dim = dt.dt.days_in_month
    tom = (dom >= dim - 1) | (dom <= 3)
    day = df["time"] // 86400
    first = (dt.dt.hour >= 1) & ((day != day.shift(1)) | (dt.dt.hour.shift(1) < 1))
    if tf == "D1":
        first = pd.Series(True, index=df.index)
    return I.sig_from(tom & first & (df["close"] > I.sma(df["close"], 20)), pd.Series(False, index=df.index))
