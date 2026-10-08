# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.375",
    "name": "Keltner Width MACD Sync",
    "concept": "เข้าเทรดด้วยจุดตัดของ MACD ในขณะที่ความผันผวนของ Keltner Channel ขยายตัวสูงกว่าปกติ (Z-Score > 1.5)",
    "logic": "MACD มักให้สัญญาณหลอกในตลาด Sideway แต่การกรองด้วยความกว้างของ Keltner Channel ที่เพิ่มสูงผิดปกติ (Z-Score > 1.5) เป็นการยืนยันว่าจุดตัดนี้เกิดในช่วงที่มีความผันผวนเพียงพอที่จะเป็นเทรนด์ใหม่, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    kl, km, ku = ind.keltner(df, n=20, k=1.5, atr_n=20)
    m, sig, hist = ind.macd(df["close"])
    ema200 = ind.ema(df["close"], 200)
    
    k_width = (ku - kl) / km.replace(0, np.nan)
    k_width_z = ind.zscore(k_width, 50)
    
    vol_high = k_width_z > 1.5
    
    buy_cond = ind.cross_up(m, sig) & vol_high & (df["close"] > ema200)
    sell_cond = ind.cross_dn(m, sig) & vol_high & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
