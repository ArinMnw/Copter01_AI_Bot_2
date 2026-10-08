# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.387",
    "name": "EMA Golden Cross Overbought",
    "concept": "เข้าเทรดจังหวะที่ EMA ตัดกันเป็นขาขึ้น (Golden Cross) โดยมีเงื่อนไขว่า Stochastic ต้องอยู่ในโซน Overbought เพื่อยืนยันความแข็งแกร่งสูงสุด",
    "logic": "ปกติ Golden Cross มักจะช้าเกินไป แต่ถ้าตอนที่มันตัดกันราคามีโมเมนตัมรุนแรงจนลาก Stochastic ให้ทะลุ 80 ได้ แปลว่านี่ไม่ใช่การตัดหลอกในไซด์เวย์ แต่เป็นต้นรอบของเทรนด์ใหญ่ที่แท้จริง, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    ema20 = ind.ema(df["close"], 20)
    ema50 = ind.ema(df["close"], 50)
    ema200 = ind.ema(df["close"], 200)
    k, d = ind.stoch(df, 14, 3, 3)
    
    buy_cond = ind.cross_up(ema20, ema50) & (k > 80.0) & (df["close"] > ema200)
    sell_cond = ind.cross_dn(ema20, ema50) & (k < 20.0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
