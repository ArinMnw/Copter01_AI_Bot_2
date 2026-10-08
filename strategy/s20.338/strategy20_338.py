# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.338",
    "name": "MACD Histogram Z-Score Reversal",
    "concept": "หาจังหวะที่ MACD Histogram แกว่งตัวรุนแรงผิดปกติ (Z-Score > 2.5) แล้วเริ่มวกกลับในทิศทางของเทรนด์หลัก",
    "logic": "การที่ Histogram ยืดตัวไปไกลมากๆ มักจะตามมาด้วยการพักตัวหรือกลับตัวระยะสั้น การแปลงเป็น Z-Score ทำให้หาง่ายขึ้น กรองเทรนด์ด้วย EMA200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    m, sig, hist = ind.macd(df["close"])
    hist_z = ind.zscore(hist, 50)
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = ind.cross_up(hist_z, -2.5) & (df["close"] > ema200)
    sell_cond = ind.cross_dn(hist_z, 2.5) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
