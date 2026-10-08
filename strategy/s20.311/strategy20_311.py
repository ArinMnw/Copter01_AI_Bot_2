# -*- coding: utf-8 -*-
"""S20.311 — Relative Volatility Index (RVI) Momentum

แนวคิด: Donald Dorsey's RVI วัดทิศทางของความผันผวน โดยใช้ Standard Deviation แทน Price Change แบบใน RSI
เมื่อ RVI ตัด 50 ขึ้นแสดงว่า Volatility กำลังขยายตัวในทิศทางบวก และเมื่อตัด 50 ลงคือทิศทางลบ
ร่วมกับ SMA(50) เพื่อกรองเทรนด์หลัก
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {
    'sid': '20.311',
    'name': 'Relative Volatility Index (RVI) Momentum',
    'concept': 'คำนวณ RVI จาก StdDev(10) ขาขึ้นและลง smoothed ด้วย EMA(14) เข้าเทรดเมื่อ RVI ตัด 50 ตามทิศทาง SMA(50)',
    'logic': 'Momentum Indicator ที่จับ Volatility Breakout ใช้ RR ปานกลาง (1.5) และทนถือข้ามวัน (24 แท่ง)',
    'sl_atr': 2.0,
    'rr': 1.5,
    'max_hold': 24,
    'be_r': 1.0
}

def generate(df, tf):
    sd = df["close"].rolling(10, min_periods=10).std(ddof=0)
    up = pd.Series(np.where(df["close"] > df["close"].shift(1), sd, 0.0), index=df.index)
    dn = pd.Series(np.where(df["close"] < df["close"].shift(1), sd, 0.0), index=df.index)
    
    ema_up = I.ema(up, 14)
    ema_dn = I.ema(dn, 14)
    
    rvi = 100 * ema_up / (ema_up + ema_dn).replace(0, np.nan)
    
    sma50 = I.sma(df["close"], 50)
    
    buy = I.cross_up(rvi, 50) & (df["close"] > sma50)
    sell = I.cross_dn(rvi, 50) & (df["close"] < sma50)
    
    return I.sig_from(buy, sell)
