# -*- coding: utf-8 -*-
"""S20.268 — Previous-Month High/Low Breakout

แนวคิด: ราคาปิดทะลุ high ของเดือนก่อนเป็นครั้งแรกในเดือน → BUY (breakout ระดับ macro); หลุด low ของเดือนก่อนครั้งแรก → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.268', 'name': 'Previous-Month High/Low Breakout', 'concept': 'ราคาปิดทะลุ high ของเดือนก่อนเป็นครั้งแรกในเดือน → BUY (breakout ระดับ macro); หลุด low ของเดือนก่อนครั้งแรก → SELL', 'sl_atr': 2.0, 'rr': 2.0, 'max_hold': 60}


def generate(df, tf):
    dt = pd.to_datetime(df["time"], unit="s")
    mk = (dt.dt.year * 12 + dt.dt.month).astype(np.int64)
    ph, pl, _, _ = I.prev_period_hl(df, mk)
    c = df["close"]
    up = c > ph; dn = c < pl
    return I.sig_from(up & (up.astype(int).groupby(mk).cumsum() == 1), dn & (dn.astype(int).groupby(mk).cumsum() == 1))
