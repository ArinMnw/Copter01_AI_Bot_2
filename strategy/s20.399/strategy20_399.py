# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.399",
    "name": "ADX Slope Momentum Shift",
    "concept": "เข้าเทรดในจังหวะที่เทรนด์เริ่มกลับมามีความแรง (ADX Slope พลิกกลับเป็นบวก) หลังจากพักตัวมาระยะหนึ่ง",
    "logic": "ปกติเราดูแค่ค่า ADX ว่าเกิน 20 หรือ 25 แต่การดูความชัน (Linear Regression Slope) ของ ADX จะช่วยจับโมเมนตัมล่วงหน้าได้ เมื่อ ADX Slope ตัดศูนย์ขึ้นแปลว่าเทรนด์กำลังเร่งความเร็ว หากทิศทางสอดคล้องกับ DMI และ EMA 200 จะเป็นจุดเข้าต้นเทรนด์ย่อยที่คมกริบ, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    pdi, ndi, adx = ind.dmi(df, 14)
    adx_slope = ind.linreg_slope(adx, 14)
    ema200 = ind.ema(df["close"], 200)
    
    # ADX ชันขึ้นหมายถึงเทรนด์แรงขึ้น (ไม่ว่าขาขึ้นหรือลง)
    accel = ind.cross_up(adx_slope, 0.0)
    
    buy_cond = accel & (pdi > ndi) & (adx > 20.0) & (df["close"] > ema200)
    sell_cond = accel & (ndi > pdi) & (adx > 20.0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
