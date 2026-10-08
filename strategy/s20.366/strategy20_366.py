# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.366",
    "name": "Stoch RSI Dual Pullback",
    "concept": "เข้าเทรดเมื่อ Indicator ยอดฮิตทั้ง RSI และ Stochastic แสดงการ Oversold/Overbought พร้อมกัน ในทิศทางตามเทรนด์หลัก",
    "logic": "ใช้การย่อตัวลึกที่คอนเฟิร์มทั้งจาก RSI (<40) และ Stochastic (<30) เพื่อสร้างจุดเข้า Mean Reversion ภายในเทรนด์ใหญ่ (EMA 200) โดยรอให้ Stochastic หักหัวตัดกันก่อนเพื่อความชัวร์, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    rsi = ind.rsi(df["close"], 14)
    k, d = ind.stoch(df, 14, 3, 3)
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = ind.cross_up(k, d) & (k < 30.0) & (rsi < 40.0) & (df["close"] > ema200)
    sell_cond = ind.cross_dn(k, d) & (k > 70.0) & (rsi > 60.0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
