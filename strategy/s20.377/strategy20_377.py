# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.377",
    "name": "Keltner Dual Channel Breakout",
    "concept": "เข้าเทรดเมื่อราคาทะลุ Keltner Channel ชั้นแรก (1.0 SD) แต่ยังไม่หลุดกรอบชั้นที่สอง (2.0 SD)",
    "logic": "การใช้ Keltner 2 ชั้นช่วยกรองความแรงของเทรนด์ การทะลุชั้น 1.0 แปลว่าเริ่มมีโมเมนตัมชัดเจน แต่ถ้าทะลุชั้น 2.0 ไปแล้วอาจจะแปลว่า Overbought/Oversold เกินไป การซื้อในโซนระหว่าง 1.0 กับ 2.0 คือจังหวะที่ได้เปรียบที่สุดในเทรนด์ใหม่, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    kl1, km1, ku1 = ind.keltner(df, n=20, k=1.0, atr_n=20)
    kl2, km2, ku2 = ind.keltner(df, n=20, k=2.0, atr_n=20)
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = ind.cross_up(df["close"], ku1) & (df["close"] < ku2) & (df["close"] > ema200)
    sell_cond = ind.cross_dn(df["close"], kl1) & (df["close"] > kl2) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
