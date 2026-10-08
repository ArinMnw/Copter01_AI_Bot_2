# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.379",
    "name": "DMI Strong Trend Re-entry",
    "concept": "เข้าเทรดจังหวะย่อตัวแล้วเด้งกลับ (Re-entry) ในช่วงที่ตลาดมีเทรนด์ที่แข็งแกร่งมากยืนยันโดย ADX",
    "logic": "การที่มี ADX > 30 หมายถึงเทรนด์ทรงพลังมาก หากราคาย่อหลุดเส้น EMA 20 แล้วสามารถตัดกลับขึ้นมาได้ในขณะที่ PDI > NDI จะเป็นจังหวะ Re-entry ที่มีโอกาสชนะสูง, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    pdi, ndi, adx = ind.dmi(df, 14)
    ema20 = ind.ema(df["close"], 20)
    ema200 = ind.ema(df["close"], 200)
    
    strong_trend = (adx > 30.0)
    
    buy_cond = strong_trend & (pdi > ndi) & ind.cross_up(df["close"], ema20) & (df["close"] > ema200)
    sell_cond = strong_trend & (ndi > pdi) & ind.cross_dn(df["close"], ema20) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
