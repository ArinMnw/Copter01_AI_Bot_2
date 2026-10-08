# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.351",
    "name": "Linear Reg Pullback Reversal",
    "concept": "เข้าเทรดเมื่อความชัน (Slope) ของ Linear Regression ติดลบ/บวกมาระยะหนึ่งแล้วพลิกกลับมาตัดศูนย์ ในทิศทางเดียวกับเทรนด์หลัก",
    "logic": "Slope ที่ติดลบในเทรนด์ขาขึ้นคือการย่อตัว (Pullback) เมื่อ Slope ตัด 0 ขึ้นมา แสดงว่าการย่อตัวจบลงและราคากำลังกลับไปทำ Higher High, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    slope = ind.linreg_slope(df["close"], 14)
    ema200 = ind.ema(df["close"], 200)
    
    # ย่อตัวลงมาอย่างน้อย 2 แท่ง
    was_down = (slope.shift(1) < 0) & (slope.shift(2) < 0)
    was_up = (slope.shift(1) > 0) & (slope.shift(2) > 0)
    
    buy_cond = ind.cross_up(slope, 0.0) & was_down & (df["close"] > ema200)
    sell_cond = ind.cross_dn(slope, 0.0) & was_up & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
