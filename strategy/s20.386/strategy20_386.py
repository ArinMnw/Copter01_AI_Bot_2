# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.386",
    "name": "LinReg Accel Stoch Sync",
    "concept": "เข้าเทรดเมื่อความชันของ Linear Regression เร่งตัวขึ้นสอดคล้องกับจังหวะการตัดกันของ Stochastic",
    "logic": "Slope ที่เพิ่มขึ้นต่อเนื่อง (Acceleration) บ่งบอกถึงความแข็งแกร่งของเทรนด์ที่แท้จริง การเข้าเทรดตอนที่เกิด Acceleration พร้อมกับ Stochastic ตัดขึ้น จะทำให้ได้จังหวะที่ลงตัวทั้งในด้านเทรนด์และโมเมนตัม, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    slope = ind.linreg_slope(df["close"], 14)
    k, d = ind.stoch(df, 14, 3, 3)
    ema200 = ind.ema(df["close"], 200)
    
    slope_accel = slope > slope.shift(1)
    slope_decel = slope < slope.shift(1)
    
    buy_cond = (slope > 0.0) & slope_accel & ind.cross_up(k, d) & (df["close"] > ema200)
    sell_cond = (slope < 0.0) & slope_decel & ind.cross_dn(k, d) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
