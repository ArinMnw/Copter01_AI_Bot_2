# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.336",
    "name": "Linear Regression R-Squared Momentum",
    "concept": "เข้าเทรดเมื่อค่า R-Squared ของ Linear Regression พุ่งทะลุ 0.7 ซึ่งแสดงว่าเกิดเทรนด์ที่ชัดเจนและแข็งแกร่ง",
    "logic": "R-Squared วัดความสมบูรณ์ของเทรนด์ (Goodness of Fit) ถ้ายกตัวสูงเกิน 0.7 แปลว่าราคาเรียงตัวเป็นเส้นตรงชัดเจน กรองด้วย EMA200 ว่าเป็นทิศไหน, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    r2 = ind.linreg_r2(df["close"], 20)
    ema200 = ind.ema(df["close"], 200)
    
    r2_break = ind.cross_up(r2, 0.7)
    
    buy_cond = r2_break & (df["close"] > ema200) & (df["close"] > df["open"])
    sell_cond = r2_break & (df["close"] < ema200) & (df["close"] < df["open"])
    
    return ind.sig_from(buy_cond, sell_cond)
