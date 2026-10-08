# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.344",
    "name": "RSI Regime Shift Breakout",
    "concept": "เข้าเทรดเมื่อฐานของ RSI ยกตัวขึ้นหรือกดต่ำลงอย่างชัดเจน (Regime Shift) บ่งบอกถึงการเปลี่ยนพฤติกรรมตลาด",
    "logic": "ในเทรนด์ขาขึ้นที่แข็งแกร่ง RSI จะแกว่งตัวในกรอบ 40-80 ถ้าราคาเลี้ยงตัวไม่ให้ RSI หลุด 40 ได้นานพอ แล้วเบรค 60 ขึ้นไป แสดงว่าแรงซื้อคุมตลาดเบ็ดเสร็จ, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    rsi = ind.rsi(df["close"], 14)
    ema200 = ind.ema(df["close"], 200)
    
    rsi_min_20 = ind.lowest(rsi.shift(1), 20)
    rsi_max_20 = ind.highest(rsi.shift(1), 20)
    
    buy_cond = ind.cross_up(rsi, 60.0) & (rsi_min_20 > 40.0) & (df["close"] > ema200)
    sell_cond = ind.cross_dn(rsi, 40.0) & (rsi_max_20 < 60.0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
