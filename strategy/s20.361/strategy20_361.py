# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.361",
    "name": "RSI MA Trend Cross",
    "concept": "เข้าเทรดเมื่อโมเมนตัมของ RSI ตัดเส้นค่าเฉลี่ยของตัวเอง (RSI MA) ในทิศทางเดียวกับเทรนด์หลัก",
    "logic": "RSI ที่ตัดเส้นค่าเฉลี่ยของตัวเองเป็นสัญญาณเบื้องต้นของการเปลี่ยนโมเมนตัม เมื่อใช้ร่วมกับเทรนด์แข็งแกร่ง (EMA 20 > 50 > 200) จะได้จุดเข้าที่มีความแม่นยำสูง, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    rsi = ind.rsi(df["close"], 14)
    rsi_ma = ind.sma(rsi, 14)
    
    ema20 = ind.ema(df["close"], 20)
    ema50 = ind.ema(df["close"], 50)
    ema200 = ind.ema(df["close"], 200)
    
    uptrend = (ema20 > ema50) & (df["close"] > ema200)
    downtrend = (ema20 < ema50) & (df["close"] < ema200)
    
    buy_cond = ind.cross_up(rsi, rsi_ma) & uptrend
    sell_cond = ind.cross_dn(rsi, rsi_ma) & downtrend
    
    return ind.sig_from(buy_cond, sell_cond)
