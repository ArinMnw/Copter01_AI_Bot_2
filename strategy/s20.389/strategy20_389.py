# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.389",
    "name": "MACD Histogram Hook Pullback",
    "concept": "เข้าเทรดเมื่อโมเมนตัมการย่อตัวเริ่มลดลง (MACD Histogram เกิดการงัดขึ้นหรือ Hook) ในขณะที่ตลาดยังอยู่ในเทรนด์",
    "logic": "MACD Histogram ที่อยู่ต่ำกว่าศูนย์แปลว่ามีแรงขายกดดันระยะสั้น แต่เมื่อมันเริ่มหักหัวกลับ (Hook Up) แสดงว่าแรงขายนั้นอ่อนกำลังลงแล้ว หากเทรนด์หลัก (EMA 200) ยังเป็นขาขึ้น นี่คือสัญญาณล่วงหน้าว่าราคาเตรียมกลับไปทำ High ใหม่, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    m, sig, hist = ind.macd(df["close"])
    ema200 = ind.ema(df["close"], 200)
    
    # Hook Up: วันนี้มากกว่าเมื่อวาน แต่เมื่อวานน้อยกว่าวันซืน (เพิ่งหักหัวขึ้น)
    hook_up = (hist > hist.shift(1)) & (hist.shift(1) < hist.shift(2))
    hook_dn = (hist < hist.shift(1)) & (hist.shift(1) > hist.shift(2))
    
    buy_cond = hook_up & (hist < 0.0) & (df["close"] > ema200)
    sell_cond = hook_dn & (hist > 0.0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
