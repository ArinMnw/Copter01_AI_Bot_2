# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.365",
    "name": "MACD Signal ADX Sync",
    "concept": "เข้าเทรดเมื่อ MACD ตัดเส้น Signal เพื่อเริ่มเวฟใหม่ โดยมีแรงส่งจาก ADX คอนเฟิร์มว่านี่คือเทรนด์จริงๆ",
    "logic": "MACD Cross มักมี False Signal เยอะในจังหวะ Sideway การบังคับใช้ ADX > 25 พร้อมฝั่ง DMI สอดคล้อง จะทำให้ได้เฉพาะ MACD Cross ที่เกิดในจังหวะระเบิดเทรนด์, กรองทิศทางด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    m, sig, hist = ind.macd(df["close"])
    pdi, ndi, adx = ind.dmi(df, 14)
    ema200 = ind.ema(df["close"], 200)
    
    strong_trend = adx > 25.0
    
    buy_cond = ind.cross_up(m, sig) & strong_trend & (pdi > ndi) & (df["close"] > ema200)
    sell_cond = ind.cross_dn(m, sig) & strong_trend & (ndi > pdi) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
