# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.396",
    "name": "DMI HA Green Re-entry",
    "concept": "เข้าเทรดรอบย่อตัวในเทรนด์แข็งแกร่ง (DMI) โดยใช้สีของ Heikin-Ashi ยืนยันการจบ Pullback",
    "logic": "ในเทรนด์ที่ ADX > 25 และ PDI > NDI หากราคาเกิดการย่อตัวจน HA เปลี่ยนเป็นสีแดง (HC < HO) การรอให้ HA เปลี่ยนกลับเป็นสีเขียวอีกครั้ง (HC ตัด HO ขึ้น) จะเป็นการยืนยันว่าการย่อตัวจบลงแล้วและพร้อมไปต่อตามเทรนด์, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    ho, hh, hl, hc = ind.heikin_ashi(df)
    pdi, ndi, adx = ind.dmi(df, 14)
    ema200 = ind.ema(df["close"], 200)
    
    strong_trend = adx > 25.0
    
    buy_cond = strong_trend & (pdi > ndi) & ind.cross_up(hc, ho) & (df["close"] > ema200)
    sell_cond = strong_trend & (ndi > pdi) & ind.cross_dn(hc, ho) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
