# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.349",
    "name": "BB Keltner Squeeze Breakout",
    "concept": "เทรด Breakout จากจุดที่มีการบีบตัวรุนแรง (Squeeze) โดยเช็คว่า Bollinger Bands หดตัวเข้าไปอยู่ใน Keltner Channel",
    "logic": "เมื่อความผันผวนลดลงจน BB (2.0) เข้าไปอยู่ใน Keltner (1.5) ตลาดกำลังสะสมพลังงาน หากราคาทะลุ Keltner ออกไปพร้อมกับทิศทางของ EMA200 มักจะเป็นจุดเริ่มต้นของเทรนด์รอบใหญ่, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    bl, bm, bu = ind.bbands(df["close"], n=20, k=2.0)
    kl, km, ku = ind.keltner(df, n=20, k=1.5, atr_n=20)
    ema200 = ind.ema(df["close"], 200)
    
    is_squeeze = (bu < ku) & (bl > kl)
    
    buy_cond = is_squeeze.shift(1) & (df["close"] > ku) & (df["close"] > ema200)
    sell_cond = is_squeeze.shift(1) & (df["close"] < kl) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
