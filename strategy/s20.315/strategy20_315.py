# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.315",
    "name": "ATR Z-Score Extreme Keltner Fade",
    "concept": "เข้าเทรดสวนเมื่อราคาหลุด Keltner Channel ช่วงที่ความผันผวนสูงผิดปกติ (ATR Z-Score > 2.0)",
    "logic": "SL 1.5 ATR เผื่อหางเทียนตอนผันผวน, RR 1.5 หวังผลดีดกลับเข้าหาเส้นกลาง Keltner, ถือ 24 แท่งเพราะ reversal ในช่วงผันผวนมักจะจบเร็วใน 1 วัน",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 0.0
}

def generate(df, tf):
    atr_14 = ind.atr(df, 14)
    atr_z = ind.zscore(atr_14, 50)
    kl, km, ku = ind.keltner(df, n=20, k=2.5, atr_n=14)
    close = df["close"]
    
    high_vol = atr_z > 2.0
    buy_cond = high_vol & (close < kl)
    sell_cond = high_vol & (close > ku)
    
    return ind.sig_from(buy_cond, sell_cond)
