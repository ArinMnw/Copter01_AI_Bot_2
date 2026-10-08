# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.368",
    "name": "Linear Reg Trend Acceleration",
    "concept": "เข้าเทรดเมื่อความชันของ Linear Regression เปลี่ยนทิศและเร่งความเร็วขึ้นอย่างชัดเจน (Acceleration)",
    "logic": "Slope ของ Linear Regression สะท้อนโมเมนตัมแบบสมูท หาก Slope ตัดจากลบเป็นบวก และยังเพิ่มค่าขึ้นต่อเนื่อง (เร่งตัว) แปลว่าเทรนด์ใหม่มีพลังจริง, กรองทิศทางด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    slope = ind.linreg_slope(df["close"], 14)
    ema200 = ind.ema(df["close"], 200)
    
    # ความชันเริ่มเป็นบวกและเร่งตัวขึ้น (บวกมากกว่าแท่งที่แล้ว และแท่งที่แล้วบวกมากกว่า 2 แท่งก่อน ซึ่งเคยติดลบ)
    buy_cond = (slope > 0) & (slope > slope.shift(1)) & (slope.shift(1) > slope.shift(2)) & (slope.shift(2) < 0) & (df["close"] > ema200)
    sell_cond = (slope < 0) & (slope < slope.shift(1)) & (slope.shift(1) < slope.shift(2)) & (slope.shift(2) > 0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
