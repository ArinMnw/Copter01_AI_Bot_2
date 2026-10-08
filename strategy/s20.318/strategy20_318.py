# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.318",
    "name": "VWMA and SMA Volume Trend",
    "concept": "เปรียบเทียบ Volume-Weighted MA (VWMA) กับ SMA ธรรมดา เพื่อดูว่า Volume สนับสนุนฝั่งไหนมากกว่ากัน",
    "logic": "เมื่อ VWMA > SMA แปลว่าแท่งที่ปิดบวกมี Volume หนาแน่นกว่า, เข้าเทรดตามทิศทาง cross, SL 1.5 ATR ตามมาตรฐาน, RR 1.5 ปิดทำกำไรเร็ว, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def vwma(df, n):
    cv = df["close"] * df["tick_volume"]
    return cv.rolling(n).sum() / df["tick_volume"].rolling(n).sum()

def generate(df, tf):
    v20 = vwma(df, 20)
    s20 = ind.sma(df["close"], 20)
    
    # Trend filter
    ema50 = ind.ema(df["close"], 50)
    
    buy_cond = ind.cross_up(v20, s20) & (df["close"] > ema50)
    sell_cond = ind.cross_dn(v20, s20) & (df["close"] < ema50)
    
    return ind.sig_from(buy_cond, sell_cond)
