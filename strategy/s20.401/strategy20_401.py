# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.401",
    "name": "HA Keltner Breakout RSI Sync",
    "concept": "เข้าเทรดเมื่อโมเมนตัม Heikin-Ashi ทะลุกรอบ Keltner Channel ยืนยันด้วยทิศทาง RSI",
    "logic": "ใช้ราคาปิดของแท่งเทียนเฉลี่ย (Heikin-Ashi Close) เพื่อลด Noise ถ้า HC ตัดกรอบ Keltner Channel (1.5 ATR) ขึ้นไปได้ และยังเป็นสีเขียว (HC > HO) พร้อมกับ RSI > 50 ถือเป็นสัญญาณ Breakout ที่มีแนวโน้มความต่อเนื่องสูง, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    ho, hh, hl, hc = ind.heikin_ashi(df)
    kl, km, ku = ind.keltner(df, n=20, k=1.5, atr_n=20)
    rsi = ind.rsi(df["close"], 14)
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = ind.cross_up(hc, ku) & (hc > ho) & (rsi > 50.0) & (df["close"] > ema200)
    sell_cond = ind.cross_dn(hc, kl) & (hc < ho) & (rsi < 50.0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
