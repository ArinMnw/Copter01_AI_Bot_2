# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.342",
    "name": "ADX Low Volatility Breakout",
    "concept": "เข้าเทรดในช่วงที่ตลาดระเบิดตัวจากภาวะซึม (Low Volatility) อย่างรุนแรง โดยดูจากการพุ่งของ ADX จากระดับต่ำมาก",
    "logic": "เมื่อ ADX แช่อยู่ในระดับต่ำ (<15) เป็นเวลานาน แปลว่าตลาดบีบตัว (Squeeze) หาก ADX ทะลุ 20 ขึ้นมาพร้อมกับทิศทางที่สอดคล้องกับ EMA200 มักจะเป็นการเริ่มต้นเทรนด์ใหม่ที่แรง, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    pdi, ndi, adx = ind.dmi(df, 14)
    ema200 = ind.ema(df["close"], 200)
    
    # ตรวจสอบว่า ADX เคยอยู่ในโซนต่ำมาก (ซึม) ก่อนหน้านี้
    adx_min = ind.lowest(adx.shift(1), 5)
    
    # การระเบิดตัว
    adx_break = ind.cross_up(adx, 20.0) & (adx_min < 15.0)
    
    buy_cond = adx_break & (pdi > ndi) & (df["close"] > ema200)
    sell_cond = adx_break & (ndi > pdi) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
