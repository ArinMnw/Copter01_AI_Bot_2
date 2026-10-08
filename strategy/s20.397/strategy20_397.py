# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.397",
    "name": "Stoch MACD RSI Pullback",
    "concept": "เข้าเทรดรอบย่อตัวด้วยสัญญาณ 3 ชั้น (Triple Oscillator) ผสมผสาน Momentum, Trend และ Cycle",
    "logic": "ใช้ MACD เป็นตัวกรองทิศทางหลัก (Hist > 0), ใช้ RSI รักษาโซนกระทิง (RSI > 40) ไม่ให้ย่อลึกเกินไป และสุดท้ายใช้ Stochastic (Cross Up < 40) เพื่อหาจุดเข้าที่แม่นยำและราคาถูกที่สุดในรอบนั้น, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    m, sig, hist = ind.macd(df["close"])
    k, d = ind.stoch(df, 14, 3, 3)
    rsi = ind.rsi(df["close"], 14)
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = (hist > 0.0) & ind.cross_up(k, d) & (k < 40.0) & (rsi > 40.0) & (df["close"] > ema200)
    sell_cond = (hist < 0.0) & ind.cross_dn(k, d) & (k > 60.0) & (rsi < 60.0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
