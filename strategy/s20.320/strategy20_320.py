# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.320",
    "name": "Stochastic Pullback in ADX Trend",
    "concept": "หาจังหวะย่อตัวลึก (Deep Pullback) ในเทรนด์ที่แข็งแกร่งมาก โดยใช้ Stochastic ตัดกันในโซน Extreme",
    "logic": "ADX > 30 ยืนยันเทรนด์แรงมาก, การที่ Stoch ลงมาถึง Oversold/Overbought ในเทรนด์แรงมักเป็นจุดพักตัวชั่วคราว, SL 1.5 ATR ตามมาตรฐาน, RR 1.5, ถือ 36 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 36,
    "be_r": 1.0
}

def generate(df, tf):
    pdi, ndi, adx = ind.dmi(df, 14)
    k, d = ind.stoch(df, 14, 3, 3)
    
    strong_trend = adx > 30
    
    # Uptrend pullback
    uptrend = strong_trend & (pdi > ndi)
    buy_cond = uptrend & ind.cross_up(k, d) & (k < 30)
    
    # Downtrend pullback
    downtrend = strong_trend & (ndi > pdi)
    sell_cond = downtrend & ind.cross_dn(k, d) & (k > 70)
    
    return ind.sig_from(buy_cond, sell_cond)
