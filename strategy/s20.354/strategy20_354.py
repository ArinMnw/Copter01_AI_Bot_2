# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.354",
    "name": "Keltner Midline Rejection Breakout",
    "concept": "เข้าเทรดเมื่อราคาย่อตัวลงมาทดสอบเส้นกลางของ Keltner Channel แล้วเกิดการปฏิเสธราคา (Rejection) กลับไปตามเทรนด์เดิม",
    "logic": "เส้นกลาง Keltner (EMA 20) ทำหน้าที่เป็น Dynamic Support/Resistance ถ้าราคาแทงทะลุเส้นกลางแต่ปิดเหนือเส้นกลางได้เป็นแท่งเขียว (ในเทรนด์ขาขึ้น) แสดงว่ามีแรงซื้อหนุนกลับอย่างรวดเร็ว, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    kl, km, ku = ind.keltner(df, n=20, k=1.5)
    ema200 = ind.ema(df["close"], 200)
    
    # ย่อมาทดสอบเส้นกลาง และปิดกลับไปได้เป็นแท่งเขียว/แดง
    buy_cond = (df["low"] < km) & (df["close"] > km) & (df["close"] > df["open"]) & (df["close"] > ema200)
    sell_cond = (df["high"] > km) & (df["close"] < km) & (df["close"] < df["open"]) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
