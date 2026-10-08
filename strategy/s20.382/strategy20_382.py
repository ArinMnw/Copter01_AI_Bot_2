# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.382",
    "name": "LinReg Slope MACD Alignment",
    "concept": "เข้าเทรดเมื่อความชันของ Linear Regression เปลี่ยนทิศเป็นบวก โดยมี MACD ในสภาวะ Bullish เต็มตัวสนับสนุน",
    "logic": "Linear Regression Slope ที่ตัดศูนย์ขึ้นแปลว่าเส้นแนวโน้มเริ่มชี้ขึ้น หากเกิดในตอนที่ MACD > 0 (เทรนด์หลักดี) และ MACD Histogram > 0 (โมเมนตัมกำลังเพิ่มขึ้น) จะทำให้สัญญาณมีความแม่นยำสูง, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    slope = ind.linreg_slope(df["close"], 14)
    m, sig, hist = ind.macd(df["close"])
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = ind.cross_up(slope, 0.0) & (m > 0.0) & (hist > 0.0) & (df["close"] > ema200)
    sell_cond = ind.cross_dn(slope, 0.0) & (m < 0.0) & (hist < 0.0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
