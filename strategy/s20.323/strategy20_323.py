# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.323",
    "name": "HMA-WMA-SMA Triple Trend Alignment",
    "concept": "ใช้ MA 3 ชนิดที่มีความไวต่างกัน (Hull, Weighted, Simple) เพื่อยืนยันเทรนด์ระยะสั้น กลาง และยาวพร้อมกัน",
    "logic": "SMA200 บอกเทรนด์หลัก, HMA14 ตัด WMA50 เป็นจุดเข้าที่ไวและแม่นยำกว่า SMA ทั่วไป, SL 1.5 ATR ปกป้อง, RR 1.5 หวังกำไรช่วงระเบิด, ถือ 36 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 36,
    "be_r": 1.0
}

def generate(df, tf):
    hma14 = ind.hma(df["close"], 14)
    wma50 = ind.wma(df["close"], 50)
    sma200 = ind.sma(df["close"], 200)
    
    close = df["close"]
    
    # Uptrend
    uptrend = close > sma200
    buy_cond = uptrend & ind.cross_up(hma14, wma50)
    
    # Downtrend
    downtrend = close < sma200
    sell_cond = downtrend & ind.cross_dn(hma14, wma50)
    
    return ind.sig_from(buy_cond, sell_cond)
