# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.405",
    "name": "LinReg Strong Trend Start",
    "concept": "เข้าเทรดเมื่อค่า R-Squared ทะลุระดับ 0.7 บ่งบอกถึงการเข้าสู่เทรนด์ที่แข็งแกร่งอย่างเป็นทางการ",
    "logic": "R-Squared เป็นค่าทางสถิติที่บอกว่าราคาเกาะติดเส้น Linear Regression มากแค่ไหน ค่าที่ตัด 0.7 ขึ้นไปแปลว่า Noise ในตลาดลดลงและเปลี่ยนเป็นเทรนด์ทิศทางเดียวอย่างชัดเจน เราจะเข้าเทรดตามทิศทางของ Slope และ EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    r2 = ind.linreg_r2(df["close"], 14)
    slope = ind.linreg_slope(df["close"], 14)
    ema200 = ind.ema(df["close"], 200)
    
    strong_trend_start = ind.cross_up(r2, 0.7)
    
    buy_cond = strong_trend_start & (slope > 0.0) & (df["close"] > ema200)
    sell_cond = strong_trend_start & (slope < 0.0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
