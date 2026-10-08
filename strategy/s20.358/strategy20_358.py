# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.358",
    "name": "HMA Turnaround Continuation",
    "concept": "เข้าเทรดจังหวะที่เทรนด์หลักยังอยู่ แต่ HMA ระยะสั้นเพิ่งทำจุดต่ำสุด/สูงสุดแล้ววกกลับ (Turnaround)",
    "logic": "HMA จะเปลี่ยนสี (ความชันเปลี่ยน) ไวกว่าเส้นค่าเฉลี่ยอื่นๆ หาก HMA วกกลับในทิศทางเดียวกับ EMA 200 และมี RSI สนับสนุน (>50) มักจะเป็นจุดสิ้นสุดการพักตัว, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    hma_14 = ind.hma(df["close"], 14)
    ema_200 = ind.ema(df["close"], 200)
    rsi = ind.rsi(df["close"], 14)
    
    hma_diff = hma_14 - hma_14.shift(1)
    
    # HMA เปลี่ยนความชันจากลบเป็นบวก
    buy_cond = (hma_diff > 0) & (hma_diff.shift(1) < 0) & (df["close"] > ema_200) & (rsi > 50.0)
    sell_cond = (hma_diff < 0) & (hma_diff.shift(1) > 0) & (df["close"] < ema_200) & (rsi < 50.0)
    
    return ind.sig_from(buy_cond, sell_cond)
