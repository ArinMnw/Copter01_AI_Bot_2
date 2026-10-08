# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.337",
    "name": "Confirmed Pivot Breakout Trend",
    "concept": "เทรด Breakout แนวต้าน/รับเดิม โดยอ้างอิงจากจุด Confirmed Pivot High/Low ล่าสุด",
    "logic": "Pivot ที่ผ่านการคอนเฟิร์ม (ซ้าย 3 ขวา 3) ถือเป็นแนวรับแนวต้านที่แข็งแกร่ง เมื่อราคาทะลุผ่านและสอดคล้องกับเทรนด์ EMA200 จะเป็นการระเบิดไปต่อ, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    ph = ind.confirmed_pivot_high(df, 3, 3).ffill()
    pl = ind.confirmed_pivot_low(df, 3, 3).ffill()
    
    ema200 = ind.ema(df["close"], 200)
    
    # Buy when close crosses above the last pivot high
    buy_cond = ind.cross_up(df["close"], ph) & (df["close"] > ema200)
    
    # Sell when close crosses below the last pivot low
    sell_cond = ind.cross_dn(df["close"], pl) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
