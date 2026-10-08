# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.367",
    "name": "Keltner Stoch Overbought Breakout",
    "concept": "เข้าเทรดทะลุขอบ Keltner Channel โดยมีเงื่อนไขว่า Stochastic ต้องอยู่ในโซน Overbought/Oversold",
    "logic": "โดยปกติ Stochastic ที่ Overbought จะแปลว่าราคาสูงไป แต่ในเทรนด์แข็งแกร่ง (ราคาเบรค Keltner Upper) การที่ Stochastic Overbought คือการยืนยันถึงความรุนแรงของแรงซื้อ (Strong Momentum), กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    kl, km, ku = ind.keltner(df, n=20, k=1.5, atr_n=20)
    k, d = ind.stoch(df, 14, 3, 3)
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = ind.cross_up(df["close"], ku) & (k > 80.0) & (k > d) & (df["close"] > ema200)
    sell_cond = ind.cross_dn(df["close"], kl) & (k < 20.0) & (k < d) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
