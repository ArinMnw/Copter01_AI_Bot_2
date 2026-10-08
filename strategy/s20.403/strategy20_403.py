# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.403",
    "name": "Stoch HA Bottom Fishing",
    "concept": "เข้าเทรดดักจับรอบย่อตัวลึกด้วยสัญญาณ Heikin-Ashi กลับตัวในโซนล่างของ Stochastic",
    "logic": "เมื่อ Stochastic อยู่ในระดับต่ำ (< 50) แสดงว่าราคาได้ย่อลงมาพอสมควร การเกิดแท่ง Heikin-Ashi สีเขียวแรก (HC ตัด HO ขึ้น) ในโซนนี้ ถือเป็นจุดกลับตัวที่สวยงามและได้เปรียบ (Bottom Fishing ในแนวโน้มขาขึ้นของ EMA 200), SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    k, d = ind.stoch(df, 14, 3, 3)
    ho, hh, hl, hc = ind.heikin_ashi(df)
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = (k > d) & (k < 50.0) & ind.cross_up(hc, ho) & (df["close"] > ema200)
    sell_cond = (k < d) & (k > 50.0) & ind.cross_dn(hc, ho) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
