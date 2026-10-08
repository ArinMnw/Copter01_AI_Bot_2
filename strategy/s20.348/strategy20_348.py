# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.348",
    "name": "Stochastic Oversold Trend Pullback",
    "concept": "เข้าเทรดจังหวะย่อตัวในเทรนด์แข็งแกร่ง โดยรอให้ Stochastic เข้าโซน Oversold/Overbought แล้ววกกลับ",
    "logic": "ในตลาดที่มีเทรนด์ชัดเจน (ADX > 25) การย่อตัวจน Stochastic ต่ำกว่า 20 ถือเป็นโอกาสเข้าซื้อของถูก (Buy the Dip) เมื่อ %K ตัด 20 ขึ้นไปหมายถึงแรงขายจบลง, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    k, d = ind.stoch(df, 14, 3, 3)
    pdi, ndi, adx = ind.dmi(df, 14)
    ema200 = ind.ema(df["close"], 200)
    
    trend_strong = adx > 25
    
    buy_cond = ind.cross_up(k, 20.0) & trend_strong & (pdi > ndi) & (df["close"] > ema200)
    sell_cond = ind.cross_dn(k, 80.0) & trend_strong & (ndi > pdi) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
