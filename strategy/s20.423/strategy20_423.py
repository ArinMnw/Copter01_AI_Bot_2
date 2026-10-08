# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.423",
    "name": "LinReg MACD Pullback",
    "concept": "เข้าเทรดเมื่อราคาย่อตัวในแนวโน้มของ Linear Regression และ MACD เริ่มกลับตัว",
    "logic": "เช็คแนวโน้มด้วยความชันของ Linear Regression หากราคาย่อตัวลงมาต่ำกว่า WMA 20 แล้ว MACD Histogram ตัด 0 กลับขึ้นไป ถือเป็นจุดสิ้นสุดการย่อตัว",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    slope = ind.linreg_slope(df["close"], 20)
    wma20 = ind.wma(df["close"], 20)
    macd, macdsig, macdhist = ind.macd(df["close"], 12, 26, 9)

    buy_cond1 = slope > 0
    buy_cond2 = df["close"] < wma20
    buy_cond3 = ind.cross_up(macdhist, 0)
    buy_signal = buy_cond1 & buy_cond2 & buy_cond3

    sell_cond1 = slope < 0
    sell_cond2 = df["close"] > wma20
    sell_cond3 = ind.cross_dn(macdhist, 0)
    sell_signal = sell_cond1 & sell_cond2 & sell_cond3

    return ind.sig_from(buy_signal, sell_signal)
