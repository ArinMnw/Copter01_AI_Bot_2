# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.327",
    "name": "Keltner Flat Market Mean Reversion",
    "concept": "เทรดสวน (Mean Reversion) ที่ขอบ Keltner Channel เฉพาะในช่วงที่ตลาดไม่มีเทรนด์ (ADX ต่ำ)",
    "logic": "เมื่อ ADX < 20 ตลาดมักจะแกว่งตัวในกรอบ การชนขอบ Keltner จึงเป็นจุดกลับตัวที่แม่นยำ, กรองด้วย RSI ว่าสุดรอบ, SL 1.0 ATR (แคบเพราะเป็น Range), RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.0,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    pdi, ndi, adx = ind.dmi(df, 14)
    kl, km, ku = ind.keltner(df, n=20, k=2.0, atr_n=14)
    rsi = ind.rsi(df["close"], 14)
    
    flat_market = adx < 20
    
    buy_cond = flat_market & (df["low"] < kl) & (rsi < 40) & (df["close"] > df["open"])
    sell_cond = flat_market & (df["high"] > ku) & (rsi > 60) & (df["close"] < df["open"])
    
    return ind.sig_from(buy_cond, sell_cond)
