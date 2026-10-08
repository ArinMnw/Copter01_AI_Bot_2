# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.370",
    "name": "BB Extreme Momentum Breakout",
    "concept": "เข้าเทรดทะลุกรอบ Bollinger Bands ที่ตั้งค่าความกว้างมาก (2.5 SD) พร้อมโมเมนตัมที่รุนแรงสุดขั้ว",
    "logic": "การทะลุ BB ที่ตั้งค่า SD ไว้ถึง 2.5 หมายความว่าแรงซื้อ/ขายนั้นมีความผิดปกติและรุนแรงมาก หากมี ADX > 30 และ RSI > 70 ช่วยยืนยันว่าเข้าสู่ภาวะ Strong Trend อย่างแท้จริง, กรองทิศทางด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    bl, bm, bu = ind.bbands(df["close"], n=20, k=2.5)
    rsi = ind.rsi(df["close"], 14)
    pdi, ndi, adx = ind.dmi(df, 14)
    ema200 = ind.ema(df["close"], 200)
    
    strong_trend = adx > 30.0
    
    buy_cond = ind.cross_up(df["close"], bu) & (rsi > 70.0) & strong_trend & (df["close"] > ema200)
    sell_cond = ind.cross_dn(df["close"], bl) & (rsi < 30.0) & strong_trend & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
