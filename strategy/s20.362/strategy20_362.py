# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.362",
    "name": "Keltner Midline Stoch Pullback",
    "concept": "หาจังหวะย่อตัวเข้าหาเส้นกลาง Keltner (Mean Reversion ภายในเทรนด์) โดยดูให้ Stochastic อยู่ในโซนได้เปรียบ",
    "logic": "ในเทรนด์ขาขึ้น ถ้าราคาย่อตัวลงมาแตะเส้นกลาง Keltner และ Stochastic ยังอยู่ในระดับต่ำ (<40) เมื่อราคาสามารถตัดเส้นกลางกลับขึ้นไปได้อีกครั้ง จะเป็นจุดเข้าที่มีความปลอดภัยสูง, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    kl, km, ku = ind.keltner(df, n=20, k=1.5, atr_n=20)
    k, d = ind.stoch(df, 14, 3, 3)
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = ind.cross_up(df["close"], km) & (k < 40.0) & (df["close"] > ema200)
    sell_cond = ind.cross_dn(df["close"], km) & (k > 60.0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
