# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.390",
    "name": "ADX Pullback Stoch Re-entry",
    "concept": "เข้าเทรดด้วยสัญญาณการดึงกลับเข้าเทรนด์ (Re-entry) ในขณะที่เทรนด์หลักมีความรุนแรงทะลุพิกัด",
    "logic": "เมื่อเทรนด์แรงมาก (ADX > 40) การรอราคาย่อตัวลงมาแตะหรือหลุดเส้นค่าเฉลี่ยระยะสั้น (EMA 20) พร้อมกับ Stochastic ที่เข้าสู่เขต Oversold (< 30) แล้วตัดกลับขึ้นไป จะได้จุดเข้าที่มีราคาถูกที่สุดในเทรนด์ย่อยนั้นก่อนระเบิดตัวต่อไป, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    pdi, ndi, adx = ind.dmi(df, 14)
    ema20 = ind.ema(df["close"], 20)
    ema200 = ind.ema(df["close"], 200)
    k, d = ind.stoch(df, 14, 3, 3)
    
    strong_trend = adx > 40.0
    
    buy_cond = strong_trend & ind.cross_up(df["close"], ema20) & (k < 30.0) & (df["close"] > ema200)
    sell_cond = strong_trend & ind.cross_dn(df["close"], ema20) & (k > 70.0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
