# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.394",
    "name": "LinReg Accel RSI Sync",
    "concept": "เข้าเทรดเมื่อความชันของเทรนด์ (Linear Regression) เร่งตัวขึ้น พร้อมกับโมเมนตัมของ RSI ที่ทะลุจุดกึ่งกลาง (50)",
    "logic": "ความชันของ Linear Regression ที่เป็นบวกและเพิ่มขึ้น (Acceleration) บ่งบอกถึงความแข็งแกร่งของเทรนด์ การรอให้ RSI ตัดเส้น 50 ขึ้นในสภาวะนี้เป็นการยืนยันว่าแรงซื้อชุดใหม่ได้เข้ามาอย่างเป็นทางการ, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    slope = ind.linreg_slope(df["close"], 14)
    rsi = ind.rsi(df["close"], 14)
    ema200 = ind.ema(df["close"], 200)
    
    slope_accel = slope > slope.shift(1)
    slope_decel = slope < slope.shift(1)
    
    buy_cond = (slope > 0.0) & slope_accel & ind.cross_up(rsi, 50.0) & (df["close"] > ema200)
    sell_cond = (slope < 0.0) & slope_decel & ind.cross_dn(rsi, 50.0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
