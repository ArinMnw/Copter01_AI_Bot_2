# -*- coding: utf-8 -*-
"""S20.141 — TTM Squeeze Release (BB inside Keltner)

แนวคิด: Bollinger(20,2) หดเข้าไปอยู่ใน Keltner(20,1.5ATR) ≥6 แท่งติด แล้วหลุดออก (squeeze fire) เข้าตามทิศ momentum = slope ของ close-กลาง Donchian/SMA20
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.141', 'name': 'TTM Squeeze Release (BB inside Keltner)', 'concept': 'Bollinger(20,2) หดเข้าไปอยู่ใน Keltner(20,1.5ATR) ≥6 แท่งติด แล้วหลุดออก (squeeze fire) เข้าตามทิศ momentum = slope ของ close-กลาง Donchian/SMA20', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    bl, bm, bu = I.bbands(df["close"], 20, 2.0)
    kl, km, ku = I.keltner(df, 20, 1.5)
    sq = (bu < ku) & (bl > kl)
    run = sq.astype(int).groupby((~sq).cumsum()).cumsum()
    fire = (~sq) & sq.shift(1).fillna(False) & (run.shift(1) >= 6)
    mid = (I.highest(df["high"], 20) + I.lowest(df["low"], 20)) / 2
    mom = I.linreg_slope(df["close"] - (mid + bm) / 2, 20)
    return I.sig_from(fire & (mom > 0), fire & (mom < 0))
