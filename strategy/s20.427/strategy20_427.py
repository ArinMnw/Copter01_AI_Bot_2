# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.427",
    "name": "LinReg RSI Pullback Acceleration",
    "concept": "หาจังหวะย่อตัวแล้วกลับไปตามเทรนด์ของ Linear Regression ผ่านจุดเด้งของ RSI",
    "logic": "เช็คเทรนด์หลักด้วยความชันของ Linear Regression ร่วมกับ ADX > 20 และหาจุดที่ราคาย่อจน RSI ตัดเส้น 40 ขึ้นมา (Buy) หรือตัด 60 ลงไป (Sell)",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    slope = ind.linreg_slope(df["close"], 20)
    rsi = ind.rsi(df["close"], 14)
    pdi, ndi, adx = ind.dmi(df, 14)

    buy_cond1 = slope > 0
    buy_cond2 = adx > 20
    buy_cond3 = ind.cross_up(rsi, 40)
    buy_signal = buy_cond1 & buy_cond2 & buy_cond3

    sell_cond1 = slope < 0
    sell_cond2 = adx > 20
    sell_cond3 = ind.cross_dn(rsi, 60)
    sell_signal = sell_cond1 & sell_cond2 & sell_cond3

    return ind.sig_from(buy_signal, sell_signal)
