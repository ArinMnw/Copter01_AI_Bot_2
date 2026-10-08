# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.360",
    "name": "BB Keltner Squeeze ADX",
    "concept": "เทรด Breakout จากจุดบีบตัว (Squeeze) โดยเพิ่มตัวกรอง ADX เพื่อลด False Breakout",
    "logic": "ต่อยอดจาก Squeeze ปกติที่ BB หดตัวเข้าใน Keltner การเพิ่มเงื่อนไข ADX > 20 ในจังหวะเบรคเอาท์จะช่วยคอนเฟิร์มว่าราคาที่ทะลุออกไปมีโมเมนตัมเพียงพอที่จะเป็นเทรนด์ใหม่ ไม่ใช่แค่สะบัดหลอก, กรองเทรนด์ด้วย EMA200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    bl, bm, bu = ind.bbands(df["close"], n=20, k=2.0)
    kl, km, ku = ind.keltner(df, n=20, k=1.5, atr_n=20)
    pdi, ndi, adx = ind.dmi(df, 14)
    ema200 = ind.ema(df["close"], 200)
    
    is_squeeze = (bu < ku) & (bl > kl)
    
    buy_cond = is_squeeze.shift(1) & (df["close"] > ku) & (adx > 20.0) & (df["close"] > ema200)
    sell_cond = is_squeeze.shift(1) & (df["close"] < kl) & (adx > 20.0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
