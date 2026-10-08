# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.357",
    "name": "HMA EMA Trend Ignition",
    "concept": "เข้าเทรดเมื่อโมเมนตัมระยะสั้น (HMA 14) ตัดเส้นฐานระยะกลาง (EMA 50) โดยมีการยืนยันจาก MACD และเทรนด์หลัก",
    "logic": "HMA มีความเร็วในการตอบสนองสูง เมื่อตัด EMA 50 ขึ้นแปลว่าเกิดแรงซื้อระยะสั้นที่อาจพลิกเป็นเทรนด์ใหม่ การกรองด้วย MACD Histogram ช่วยตัดสัญญาณหลอกในช่วง Sideway, กรองด้วย EMA200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    hma_14 = ind.hma(df["close"], 14)
    ema_50 = ind.ema(df["close"], 50)
    ema_200 = ind.ema(df["close"], 200)
    
    m, sig, hist = ind.macd(df["close"])
    
    buy_cond = ind.cross_up(hma_14, ema_50) & (m > 0) & (hist > 0) & (df["close"] > ema_200)
    sell_cond = ind.cross_dn(hma_14, ema_50) & (m < 0) & (hist < 0) & (df["close"] < ema_200)
    
    return ind.sig_from(buy_cond, sell_cond)
