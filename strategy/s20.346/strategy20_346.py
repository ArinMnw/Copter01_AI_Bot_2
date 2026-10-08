# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.346",
    "name": "MACD Histogram Acceleration Breakout",
    "concept": "เข้าเทรดเมื่อ MACD Histogram ไม่ใช่แค่ตัดเส้นศูนย์ แต่มีความเร่ง (Acceleration) เพิ่มขึ้นต่อเนื่อง 3 แท่ง",
    "logic": "การที่ Histogram กว้างขึ้นต่อเนื่องบ่งบอกถึงโมเมนตัมที่กำลังขยายตัวอย่างรุนแรง หากทะลุแดนบวก/ลบในขณะที่มีความเร่ง จะเป็นการคอนเฟิร์มว่าเทรนด์ใหม่มีพลังพอที่จะไปต่อ, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    m, sig, hist = ind.macd(df["close"])
    ema200 = ind.ema(df["close"], 200)
    
    hist_diff = hist - hist.shift(1)
    
    accel_up = (hist_diff > 0) & (hist_diff.shift(1) > 0) & (hist_diff.shift(2) > 0)
    accel_dn = (hist_diff < 0) & (hist_diff.shift(1) < 0) & (hist_diff.shift(2) < 0)
    
    buy_cond = ind.cross_up(hist, 0.0) & accel_up & (df["close"] > ema200)
    sell_cond = ind.cross_dn(hist, 0.0) & accel_dn & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
