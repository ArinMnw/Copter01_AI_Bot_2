# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.410",
    "name": "LinReg Slope RSI Cross",
    "concept": "เข้าเทรดเมื่อ RSI ตัดเส้น 50 ตามทิศทางแนวโน้มของ Linear Regression",
    "logic": "ใช้ความชันของ Linear Regression เพื่อประเมินเทรนด์หลัก แล้วหาจังหวะเข้าเมื่อ Momentum (RSI) เปลี่ยนผ่านระดับ 50 เพื่อยืนยันแรงส่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    slope = ind.linreg_slope(df["close"], 20)
    rsi = ind.rsi(df["close"], 14)

    buy_cond1 = slope > 0
    buy_cond2 = ind.cross_up(rsi, 50)
    buy_signal = buy_cond1 & buy_cond2

    sell_cond1 = slope < 0
    sell_cond2 = ind.cross_dn(rsi, 50)
    sell_signal = sell_cond1 & sell_cond2

    return ind.sig_from(buy_signal, sell_signal)
