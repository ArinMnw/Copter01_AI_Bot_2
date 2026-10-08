# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.317",
    "name": "Donchian Midline Trend Bounce",
    "concept": "หาจังหวะย่อตัวในเทรนด์ใหญ่ โดยใช้จุดกึ่งกลาง Donchian Channel (Kijun-sen แบบประยุกต์) เป็นแนวรับแนวต้าน",
    "logic": "การที่ราคา Low ทะลุ Midline แต่ปิดเหนือได้ แสดงถึงแรงซื้อกลับในเทรนด์ขาขึ้น, SL 1.5 ATR ปกป้องเผื่อหลุดจริง, RR 2.0 ลุ้นทำ High ใหม่, ถือ 48 แท่งเผื่อรอบ swing ปกติ",
    "sl_atr": 1.5,
    "rr": 2.0,
    "max_hold": 48,
    "be_r": 1.0
}

def generate(df, tf):
    close = df["close"]
    low = df["low"]
    high = df["high"]
    
    ema200 = ind.ema(close, 200)
    
    hh = ind.highest(high, 20)
    ll = ind.lowest(low, 20)
    midline = (hh + ll) / 2.0
    
    # Uptrend
    uptrend = close > ema200
    # Pullback and bounce
    buy_cond = uptrend & (low < midline) & (close > midline) & (df["open"] < close)
    
    # Downtrend
    downtrend = close < ema200
    sell_cond = downtrend & (high > midline) & (close < midline) & (df["open"] > close)
    
    return ind.sig_from(buy_cond, sell_cond)
