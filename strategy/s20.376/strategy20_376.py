# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.376",
    "name": "EMA Ribbon Deep Pullback",
    "concept": "เข้าเทรดเมื่อราคาย่อตัวลงมาลึกถึงแกนกลางของ EMA Ribbon ในขณะที่ริบบิ้นยังเรียงตัวเป็นเทรนด์ชัดเจน",
    "logic": "การเรียงตัวของ EMA 8, 13, 21, 34, 55 (Ribbon) สะท้อนเทรนด์ที่แข็งแกร่งมาก หากราคาย่อตัวลงมาทะลุเส้น 8 และ 13 แล้วตัดเส้น 21 กลับขึ้นไปได้ แปลว่านี่คือการย่อเพื่อไปต่อ ไม่ใช่การเปลี่ยนเทรนด์, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    ema8 = ind.ema(df["close"], 8)
    ema13 = ind.ema(df["close"], 13)
    ema21 = ind.ema(df["close"], 21)
    ema34 = ind.ema(df["close"], 34)
    ema55 = ind.ema(df["close"], 55)
    ema200 = ind.ema(df["close"], 200)
    
    ribbon_up = (ema8 > ema13) & (ema13 > ema21) & (ema21 > ema34) & (ema34 > ema55)
    ribbon_dn = (ema8 < ema13) & (ema13 < ema21) & (ema21 < ema34) & (ema34 < ema55)
    
    buy_cond = ribbon_up & ind.cross_up(df["close"], ema21) & (df["close"] > ema200)
    sell_cond = ribbon_dn & ind.cross_dn(df["close"], ema21) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
