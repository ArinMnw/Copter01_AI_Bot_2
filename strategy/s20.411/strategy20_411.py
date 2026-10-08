# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.411",
    "name": "Volatility Squeeze MACD Breakout",
    "concept": "เข้าเทรดเมื่อราคาระเบิดออกจากช่วงพักตัว (Squeeze) โดยใช้ MACD Histogram ยืนยันทิศทาง",
    "logic": "เช็ค Squeeze โดยดูว่า Bollinger Bands แคบกว่า Keltner Channel (พักตัว) และหาจังหวะที่ MACD Histogram ตัด 0 เป็นจุดเริ่มต้นของแรงระเบิดรอบใหม่",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    bbl, bbm, bbu = ind.bbands(df["close"], 20, 2.0)
    kl, km, ku = ind.keltner(df, 20, 1.5)
    macd, macdsig, macdhist = ind.macd(df["close"], 12, 26, 9)

    # เงื่อนไข Squeeze: BB แคบกว่า Keltner (bbu < ku และ bbl > kl)
    is_squeeze = (bbu < ku) & (bbl > kl)
    
    # หรือเพิ่งหลุดจาก Squeeze มาไม่เกิน 3 แท่ง
    was_squeeze = is_squeeze.rolling(3).max() > 0

    buy_cond1 = was_squeeze
    buy_cond2 = ind.cross_up(macdhist, 0)
    buy_cond3 = df["close"] > km
    buy_signal = buy_cond1 & buy_cond2 & buy_cond3

    sell_cond1 = was_squeeze
    sell_cond2 = ind.cross_dn(macdhist, 0)
    sell_cond3 = df["close"] < km
    sell_signal = sell_cond1 & sell_cond2 & sell_cond3

    return ind.sig_from(buy_signal, sell_signal)
