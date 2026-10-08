# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.421",
    "name": "LinReg EMA Alignment Breakout",
    "concept": "เข้าเทรดเมื่อโมเมนตัมตัดเส้น 0 ไปในทิศทางเดียวกับ Linear Regression และ EMA",
    "logic": "เช็คเทรนด์หลักด้วย EMA 100 และเทรนด์ระยะกลางด้วย Linear Regression (Slope) จากนั้นรอจังหวะที่ MACD ตัดเส้น 0 ข้ามไปในฝั่งของเทรนด์ โดยมี ADX ยืนยันพละกำลัง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    ema100 = ind.ema(df["close"], 100)
    slope = ind.linreg_slope(df["close"], 20)
    macd, macdsig, macdhist = ind.macd(df["close"], 12, 26, 9)
    pdi, ndi, adx = ind.dmi(df, 14)

    buy_cond1 = df["close"] > ema100
    buy_cond2 = slope > 0
    buy_cond3 = ind.cross_up(macd, 0)
    buy_cond4 = adx > 20
    buy_signal = buy_cond1 & buy_cond2 & buy_cond3 & buy_cond4

    sell_cond1 = df["close"] < ema100
    sell_cond2 = slope < 0
    sell_cond3 = ind.cross_dn(macd, 0)
    sell_cond4 = adx > 20
    sell_signal = sell_cond1 & sell_cond2 & sell_cond3 & sell_cond4

    return ind.sig_from(buy_signal, sell_signal)
