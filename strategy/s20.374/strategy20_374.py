# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.374",
    "name": "HMA LinReg Trend Convergence",
    "concept": "เข้าเทรดเมื่อราคาทะลุเส้น HMA ในทิศทางเดียวกับความชัน (Slope) ของ Linear Regression และเทรนด์หลัก",
    "logic": "ใช้ความไวของ HMA เพื่อหาจุดเข้าเมื่อราคาเริ่มมีโมเมนตัม แต่ใช้ความชันของ Linear Regression (ระยะเวลาเท่ากัน) เพื่อยืนยันว่าทิศทางของฐานข้อมูลรวมกำลังไปทางนั้นจริง ลดการโดนสะบัดหลอก, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    hma_14 = ind.hma(df["close"], 14)
    slope = ind.linreg_slope(df["close"], 14)
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = ind.cross_up(df["close"], hma_14) & (slope > 0.0) & (df["close"] > ema200)
    sell_cond = ind.cross_dn(df["close"], hma_14) & (slope < 0.0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
