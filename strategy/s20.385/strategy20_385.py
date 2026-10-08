# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.385",
    "name": "Stoch TTM Squeeze Pullback",
    "concept": "เข้าเทรดด้วยสัญญาณย่อตัวของ Stochastic ในช่วงที่ตลาดยังคงบีบตัวสะสมพลัง (Squeeze)",
    "logic": "ปกติเรามักจะเทรดตอน Squeeze ระเบิดออก (Breakout) แต่กลยุทธ์นี้เลือกดักเข้าเทรดตอนตลาดยังอยู่ใน Squeeze แต่ทำรอบย่อตัวสั้นๆ (Stoch Cross Up < 40) เพื่อให้ได้ต้นทุนที่ต่ำสุดก่อนที่มันจะระเบิดไปตามเทรนด์ใหญ่ (EMA 200), SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    bl, bm, bu = ind.bbands(df["close"], n=20, k=2.0)
    kl, km, ku = ind.keltner(df, n=20, k=1.5, atr_n=20)
    k, d = ind.stoch(df, 14, 3, 3)
    ema200 = ind.ema(df["close"], 200)
    
    squeeze = (bu < ku) & (bl > kl)
    
    buy_cond = squeeze & ind.cross_up(k, d) & (k < 40.0) & (df["close"] > ema200)
    sell_cond = squeeze & ind.cross_dn(k, d) & (k > 60.0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
