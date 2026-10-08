# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.381",
    "name": "Stoch RSI MA Momentum Pullback",
    "concept": "เข้าเทรดด้วยสัญญาณ Oversold ของ Stochastic แต่ให้ RSI MA ทำหน้าที่คุมโซนโมเมนตัมหลักให้อยู่ฝั่งบวกเสมอ",
    "logic": "RSI ที่อยู่เหนือค่าเฉลี่ย 50 วันของตัวมันเอง (RSI MA) หมายถึงตลาดกระทิงกำลังควบคุมเกมส์ ในสภาวะนี้ การใช้ Stochastic รอจังหวะย่อตัวลึก (K < 30) แล้วตัดขึ้น จะทำให้ได้จุดเข้าที่คมและปลอดภัยกว่าการใช้เพียงเทรนด์ EMA 200 อย่างเดียว, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    rsi = ind.rsi(df["close"], 14)
    rsi_ma = ind.sma(rsi, 50)
    k, d = ind.stoch(df, 14, 3, 3)
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = (rsi > rsi_ma) & ind.cross_up(k, d) & (k < 30.0) & (df["close"] > ema200)
    sell_cond = (rsi < rsi_ma) & ind.cross_dn(k, d) & (k > 70.0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
