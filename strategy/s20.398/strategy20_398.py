# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.398",
    "name": "Fast Stoch Dip Re-entry",
    "concept": "เข้าเทรดรอบย่อตัวสั้นมากๆ (Micro-dip) ด้วย Fast Stochastic ในขณะที่เทรนด์ยังคงทรงตัวเหนือเส้นค่าเฉลี่ยระยะสั้น",
    "logic": "ใช้ Stochastic ระยะสั้น (5,3,3) เพื่อจับจังหวะสวิงย่อยๆ ถ้าราคาสามารถทรงตัวอยู่เหนือ EMA 20 ได้ในขณะที่ Fast Stoch ลงไปแตะ Oversold (<20) และตัดขึ้น นั่นคือการย่อตัวเพียงเล็กน้อยก่อนไปต่อตามเทรนด์ใหญ่, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    k, d = ind.stoch(df, 5, 3, 3)
    ema20 = ind.ema(df["close"], 20)
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = ind.cross_up(k, d) & (k < 20.0) & (df["close"] > ema20) & (ema20 > ema200)
    sell_cond = ind.cross_dn(k, d) & (k > 80.0) & (df["close"] < ema20) & (ema20 < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
