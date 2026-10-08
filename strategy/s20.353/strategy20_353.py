# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.353",
    "name": "Stochastic MACD Continuation",
    "concept": "เทรดจังหวะย่อตัวในเทรนด์แข็งแกร่ง โดยให้ Stochastic ตัดขึ้นในโซนต่ำกว่า 50 พร้อมกับ MACD คอนเฟิร์มว่ายังเป็นขาขึ้น",
    "logic": "ในเทรนด์ที่แข็งแกร่ง (MACD > 0, Hist > 0, ขอบน EMA200) การรอให้ Stochastic ตัดกันจากโซนต่ำ (< 50) หมายถึงจบการพักตัวย่อยและพร้อมวิ่งตามเทรนด์ต่อ, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    k, d = ind.stoch(df, 14, 3, 3)
    m, sig, hist = ind.macd(df["close"])
    ema200 = ind.ema(df["close"], 200)
    
    mac_bull = (m > 0) & (hist > 0) & (df["close"] > ema200)
    mac_bear = (m < 0) & (hist < 0) & (df["close"] < ema200)
    
    buy_cond = ind.cross_up(k, d) & (k < 50) & mac_bull
    sell_cond = ind.cross_dn(k, d) & (k > 50) & mac_bear
    
    return ind.sig_from(buy_cond, sell_cond)
