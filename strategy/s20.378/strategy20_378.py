# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.378",
    "name": "EMA Fast Trend Ignition",
    "concept": "เข้าเทรดด้วยจุดตัดของเส้น EMA ความเร็วสูง (8 ตัด 21) ในขณะที่เทรนด์หลัก (55 และ 200) สนับสนุน",
    "logic": "จุดตัดของ EMA 8 และ 21 มีความรวดเร็วและจับรอบสวิงเล็กๆ ได้ดี หากเราบังคับว่า EMA 21 ต้องอยู่เหนือ 55 เสมอ และราคาอยู่เหนือ 200 จะช่วยให้เราได้จังหวะเข้าทำเร็วในขณะที่เทรนด์กำลังมีความแข็งแกร่งสูงสุด, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    ema8 = ind.ema(df["close"], 8)
    ema21 = ind.ema(df["close"], 21)
    ema55 = ind.ema(df["close"], 55)
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = ind.cross_up(ema8, ema21) & (ema21 > ema55) & (df["close"] > ema200)
    sell_cond = ind.cross_dn(ema8, ema21) & (ema21 < ema55) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
