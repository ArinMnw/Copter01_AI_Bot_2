# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.334",
    "name": "Linear Regression Trend Ignition",
    "concept": "หาจังหวะที่ความชันของ Linear Regression ตัดผ่านศูนย์ พร้อมกับมีค่า R-squared สูง",
    "logic": "ความชัน (Slope) ตัดศูนย์หมายถึงราคาเริ่มเปลี่ยนทิศทาง การใช้ R-squared (> 0.5) ช่วยยืนยันว่าเป็นเทรนด์ที่แข็งแรง ไม่ใช่แค่ราคาแกว่งตัวแบบไร้ทิศทาง กรองเทรนด์ด้วย EMA200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    slope = ind.linreg_slope(df["close"], 20)
    r2 = ind.linreg_r2(df["close"], 20)
    ema200 = ind.ema(df["close"], 200)
    
    strong_trend = r2 > 0.5
    
    buy_cond = ind.cross_up(slope, 0.0) & strong_trend & (df["close"] > ema200)
    sell_cond = ind.cross_dn(slope, 0.0) & strong_trend & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
