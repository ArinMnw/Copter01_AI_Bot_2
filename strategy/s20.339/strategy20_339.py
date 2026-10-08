# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.339",
    "name": "Inside Bar MACD Continuation Breakout",
    "concept": "เทรด Breakout จากแท่ง Inside Bar (แท่งพักตัว) โดยใช้ MACD ยืนยันว่าโมเมนตัมของเทรนด์ยังคงไปต่อ",
    "logic": "Inside Bar คือการหดตัวของความผันผวน หากราคาทะลุ High/Low ของ Inside Bar ไปในทิศทางที่ MACD และ EMA200 ยืนยัน จะเป็นการระเบิดไปต่อตามเทรนด์เดิม, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    m, sig, hist = ind.macd(df["close"])
    ema200 = ind.ema(df["close"], 200)
    
    is_ib = (df["high"] < df["high"].shift(1)) & (df["low"] > df["low"].shift(1))
    
    macd_bull = (m > 0) & (hist > 0) & (df["close"] > ema200)
    macd_bear = (m < 0) & (hist < 0) & (df["close"] < ema200)
    
    prev_ib = is_ib.shift(1)
    
    # Breakout of the Inside Bar
    buy_cond = prev_ib & (df["close"] > df["high"].shift(1)) & macd_bull.shift(1)
    sell_cond = prev_ib & (df["close"] < df["low"].shift(1)) & macd_bear.shift(1)
    
    return ind.sig_from(buy_cond, sell_cond)
