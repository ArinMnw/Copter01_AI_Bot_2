# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.380",
    "name": "Keltner 3SD Exhaustion Fade",
    "concept": "เข้าเทรดสวนการกระชากที่รุนแรงมากผิดปกติ (หลุด Keltner 3.0 SD) เพื่อหวังผล Mean Reversion กลับเข้าสู่เทรนด์หลัก",
    "logic": "Keltner ที่กว้างถึง 3.0 ATR เป็นระดับที่ยากมากที่ราคาจะวิ่งไปถึง เมื่อราคาทะลุออกไปแล้ววกกลับเข้ามาได้ (Exhaustion) หมายถึงแรงฝั่งนั้นหมดลงอย่างสิ้นเชิง หากเทรดกลับเข้าหาเทรนด์หลัก (EMA 200) จะเป็นจุดเข้าที่มีความได้เปรียบสูงมาก, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    kl, km, ku = ind.keltner(df, n=20, k=3.0, atr_n=20)
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = ind.cross_up(df["close"], kl) & (df["close"] > ema200)
    sell_cond = ind.cross_dn(df["close"], ku) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
