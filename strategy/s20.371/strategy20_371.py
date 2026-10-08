# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.371",
    "name": "Volatility MACD Expansion",
    "concept": "เข้าเทรดเมื่อความผันผวน (Standard Deviation) ขยายตัวสูงกว่าค่าเฉลี่ย โดยมี MACD ช่วยบอกทิศทาง",
    "logic": "การที่ความผันผวนเพิ่มขึ้นอย่างฉับพลัน (STD ตัด STD_MA ขึ้น) มักเป็นจุดเริ่มต้นของการระเบิดราคา หากเรากรองทิศทางด้วยความแข็งแกร่งของ MACD และเทรนด์หลัก EMA 200 จะช่วยให้เกาะเทรนด์ได้ตั้งแต่ต้นน้ำ, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    std = df["close"].rolling(20).std()
    std_ma = std.rolling(20).mean()
    m, sig, hist = ind.macd(df["close"])
    ema200 = ind.ema(df["close"], 200)
    
    vol_expand = ind.cross_up(std, std_ma)
    
    buy_cond = vol_expand & (m > 0) & (hist > 0) & (df["close"] > ema200)
    sell_cond = vol_expand & (m < 0) & (hist < 0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
