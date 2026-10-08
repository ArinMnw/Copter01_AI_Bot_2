# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.416",
    "name": "PSAR Keltner Pullback",
    "concept": "เข้าเทรดช่วงย่อตัวในเทรนด์ของ PSAR โดยใช้ Keltner และ MACD ยืนยันจุดจบของการย่อตัว",
    "logic": "เช็คเทรนด์หลักด้วย Parabolic SAR ถ้าราคาย่อตัวกลับมาลึกผ่าน Keltner Middle แล้ว MACD Histogram เริ่มหันหัวกลับ (ตัด 0) แสดงว่าการย่อตัวสิ้นสุด",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sar, sar_trend = ind.psar(df, 0.02, 0.2)
    kl, km, ku = ind.keltner(df, 20, 1.5)
    macd, macdsig, macdhist = ind.macd(df["close"], 12, 26, 9)

    # Buy: PSAR เป็นขาขึ้น, ราคาอยู่ต่ำกว่า Keltner Middle, MACD Histogram เพิ่งตัดขึ้น 0
    buy_cond1 = sar_trend == 1
    buy_cond2 = df["close"] < km
    buy_cond3 = ind.cross_up(macdhist, 0)
    buy_signal = buy_cond1 & buy_cond2 & buy_cond3

    # Sell: PSAR เป็นขาลง, ราคาอยู่สูงกว่า Keltner Middle, MACD Histogram เพิ่งตัดลง 0
    sell_cond1 = sar_trend == -1
    sell_cond2 = df["close"] > km
    sell_cond3 = ind.cross_dn(macdhist, 0)
    sell_signal = sell_cond1 & sell_cond2 & sell_cond3

    return ind.sig_from(buy_signal, sell_signal)
