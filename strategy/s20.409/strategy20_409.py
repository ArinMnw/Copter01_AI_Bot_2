# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.409",
    "name": "PSAR Keltner Momentum",
    "concept": "เข้าเทรดเมื่อราคาทะลุ PSAR เปลี่ยนเทรนด์ และยืนยันด้วย Keltner Channel",
    "logic": "ใช้จังหวะที่ราคาพลิกกลับตัดผ่าน Parabolic SAR เพื่อหาจุดเริ่มต้นเทรนด์ใหม่ พร้อมกับดู ADX > 20 ว่ามีแรงส่ง และราคาต้องอยู่ถูกฝั่งของ Keltner Middle เพื่อยืนยัน",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sar, sar_trend = ind.psar(df, 0.02, 0.2)
    pdi, ndi, adx = ind.dmi(df, 14)
    ku, km, kl = ind.keltner(df, 20, 2.0)

    # Buy: ราคาตัด PSAR ขึ้นไป (หรือ trend เป็น 1 แท่งแรก), ADX > 20, ราคาอยู่เหนือ Keltner Mid
    buy_cond1 = ind.cross_up(df["close"], sar) | ((sar_trend == 1) & (sar_trend.shift(1) == -1))
    buy_cond2 = adx > 20
    buy_cond3 = df["close"] > km
    buy_signal = buy_cond1 & buy_cond2 & buy_cond3

    # Sell: ราคาตัด PSAR ลง (หรือ trend เป็น -1 แท่งแรก), ADX > 20, ราคาอยู่ใต้ Keltner Mid
    sell_cond1 = ind.cross_dn(df["close"], sar) | ((sar_trend == -1) & (sar_trend.shift(1) == 1))
    sell_cond2 = adx > 20
    sell_cond3 = df["close"] < km
    sell_signal = sell_cond1 & sell_cond2 & sell_cond3

    return ind.sig_from(buy_signal, sell_signal)
