# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.340",
    "name": "Z-Score Trend Dip Reversal",
    "concept": "ช้อนซื้อในเทรนด์ขาขึ้นเมื่อราคาทรุดตัวลงฉับพลันจนผิดปกติ (Z-Score < -2.0) แล้วเริ่มดีดกลับ",
    "logic": "ราคาในเทรนด์หลักมักจะถูกดึงกลับเข้าหาค่าเฉลี่ยเสมอ การใช้ Z-Score ตรวจจับการทรุดตัวผิดปกติทำให้ได้จุดเข้าที่มีแต้มต่อ (Discount) สูงสุด กรองด้วย EMA 20/50/200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    price_z = ind.zscore(df["close"], 20)
    ema20 = ind.ema(df["close"], 20)
    ema50 = ind.ema(df["close"], 50)
    ema200 = ind.ema(df["close"], 200)
    
    uptrend = (ema20 > ema50) & (df["close"] > ema200)
    buy_cond = ind.cross_up(price_z, -2.0) & uptrend
    
    downtrend = (ema20 < ema50) & (df["close"] < ema200)
    sell_cond = ind.cross_dn(price_z, 2.0) & downtrend
    
    return ind.sig_from(buy_cond, sell_cond)
