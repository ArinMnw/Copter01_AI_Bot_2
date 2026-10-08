# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.415",
    "name": "Bollinger Reversal ADX",
    "concept": "เทรดสวนทาง (Mean Reversion) เมื่อราคาหลุดกรอบ Bollinger Bands ในช่วงตลาดไม่มีเทรนด์",
    "logic": "เช็คสภาวะตลาดไซด์เวย์ด้วย ADX < 20 จากนั้นหาจุดเข้าเมื่อราคาหลุดขอบ Bollinger Band ด้านล่าง (Buy) หรือด้านบน (Sell) แล้วรอ Stochastic ยืนยันการกลับตัวตัดกัน",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    bbl, bbm, bbu = ind.bbands(df["close"], 20, 2.0)
    pdi, ndi, adx = ind.dmi(df, 14)
    kk, dd = ind.stoch(df, 14, 3, 3)

    # Buy: ตลาด Sideway (ADX < 20), ราคาเคยทะลุ BBL ลงไปแต่เริ่มกลับตัวโดย Stoch %K ตัด %D ขึ้น
    buy_cond1 = adx < 20
    buy_cond2 = df["low"] < bbl
    buy_cond3 = ind.cross_up(kk, dd)
    buy_signal = buy_cond1 & buy_cond2 & buy_cond3

    # Sell: ตลาด Sideway (ADX < 20), ราคาเคยทะลุ BBU ขึ้นไปแต่เริ่มกลับตัวโดย Stoch %K ตัด %D ลง
    sell_cond1 = adx < 20
    sell_cond2 = df["high"] > bbu
    sell_cond3 = ind.cross_dn(kk, dd)
    sell_signal = sell_cond1 & sell_cond2 & sell_cond3

    return ind.sig_from(buy_signal, sell_signal)
