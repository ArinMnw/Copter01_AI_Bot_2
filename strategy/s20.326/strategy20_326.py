# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.326",
    "name": "ADX Trend Acceleration Breakout",
    "concept": "เข้าเทรดเมื่อความแข็งแกร่งของเทรนด์ (ADX) เร่งตัวขึ้นอย่างรวดเร็ว (เพิ่มขึ้นเกิน 5 จุดใน 3 แท่ง)",
    "logic": "การที่ ADX ชันขึ้นอย่างรวดเร็ว (Acceleration) บ่งบอกถึงโมเมนตัมของเทรนด์ที่พุ่งแรง กรองทิศทางด้วย DMI และ RSI, SL 1.5 ATR ปกป้องหลอก, RR 1.5 หวังผลระยะสั้น, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    pdi, ndi, adx = ind.dmi(df, 14)
    rsi = ind.rsi(df["close"], 14)
    
    adx_diff_3 = adx - adx.shift(3)
    
    # Acceleration trigger
    accel = ind.cross_up(adx_diff_3, 5.0) & (adx > 25)
    
    buy_cond = accel & (pdi > ndi) & (rsi > 55)
    sell_cond = accel & (ndi > pdi) & (rsi < 45)
    
    return ind.sig_from(buy_cond, sell_cond)
