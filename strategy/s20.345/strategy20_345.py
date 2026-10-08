# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.345",
    "name": "Triple HMA Trend Breakout",
    "concept": "เข้าเทรดด้วยเส้น Hull Moving Average (HMA) 3 เส้น (9, 21, 55) เพื่อจับจุดเริ่มต้นรอบการแกว่งที่ไวและสมูทที่สุด",
    "logic": "HMA มีความเร็วในการตอบสนองมากกว่า EMA การตัดกันของ HMA 9/21 พร้อมกับการยืนยันเทรนด์ระดับกลาง (HMA 55) และระดับยาว (EMA 200) จึงเป็นจุดเข้าที่มีความแม่นยำสูง, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    hma_fast = ind.hma(df["close"], 9)
    hma_med = ind.hma(df["close"], 21)
    hma_slow = ind.hma(df["close"], 55)
    
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = ind.cross_up(hma_fast, hma_med) & (df["close"] > hma_slow) & (df["close"] > ema200)
    sell_cond = ind.cross_dn(hma_fast, hma_med) & (df["close"] < hma_slow) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
