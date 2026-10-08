# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.402",
    "name": "LinReg DMI Trend Shift",
    "concept": "เข้าเทรดเมื่อความชันของ Linear Regression ตัดศูนย์ยืนยันความสอดคล้องกับโมเมนตัมหลักจาก DMI",
    "logic": "การใช้ Linear Regression Slope ตัด 0 เพื่อบอกจุดหมุน (Pivot) ของเทรนด์ระยะสั้น หากจุดหมุนนั้นเกิดในทิศทางเดียวกับเทรนด์หลักที่วัดด้วย DMI (ADX > 25, PDI > NDI) จะช่วยให้เราได้จุดเข้าที่ได้เปรียบทั้งความเร็วและทิศทาง, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    slope = ind.linreg_slope(df["close"], 14)
    pdi, ndi, adx = ind.dmi(df, 14)
    ema200 = ind.ema(df["close"], 200)
    
    strong_trend = adx > 25.0
    
    buy_cond = ind.cross_up(slope, 0.0) & (pdi > ndi) & strong_trend & (df["close"] > ema200)
    sell_cond = ind.cross_dn(slope, 0.0) & (ndi > pdi) & strong_trend & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
