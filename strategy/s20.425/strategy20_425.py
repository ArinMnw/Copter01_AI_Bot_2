# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.425",
    "name": "Keltner Midline Momentum RSI",
    "concept": "เข้าเทรดเมื่อราคาทะลุเส้นกลางของ Keltner พร้อมแรงส่งจาก RSI และ ADX",
    "logic": "ใช้ Keltner Midline เป็นตัวแบ่งเทรนด์สั้นๆ ถ้าราคาพุ่งข้ามเส้นกลาง พร้อมกับ RSI ชี้ทางไปฝั่งเดียวกันและ ADX > 20 ยืนยันความแรงของเทรนด์",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    kl, km, ku = ind.keltner(df, 20, 1.5)
    rsi = ind.rsi(df["close"], 14)
    pdi, ndi, adx = ind.dmi(df, 14)

    buy_cond1 = ind.cross_up(df["close"], km)
    buy_cond2 = rsi > 55
    buy_cond3 = adx > 20
    buy_signal = buy_cond1 & buy_cond2 & buy_cond3

    sell_cond1 = ind.cross_dn(df["close"], km)
    sell_cond2 = rsi < 45
    sell_cond3 = adx > 20
    sell_signal = sell_cond1 & sell_cond2 & sell_cond3

    return ind.sig_from(buy_signal, sell_signal)
