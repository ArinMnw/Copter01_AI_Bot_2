# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.363",
    "name": "HA MACD Pullback",
    "concept": "เข้าเทรดเมื่อราคาย่อตัวสั้นๆ (HA สีเปลี่ยน) และกลับมาไปต่อในทิศทางเดียวกับ MACD และ EMA200",
    "logic": "ใช้สีของ Heikin-Ashi (HA) เพื่อดูการพักตัว แท่งสีแดงในเทรนด์ขาขึ้นหมายถึงการย่อ เมื่อ HA กลับมาเป็นสีเขียวอีกครั้งและ MACD Histogram สนับสนุนการไปต่อ ถือเป็นจุดสิ้นสุดการพักตัวและพร้อมวิ่งต่อ, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    ho, hh, hl, hc = ind.heikin_ashi(df)
    m, sig, hist = ind.macd(df["close"])
    ema200 = ind.ema(df["close"], 200)
    
    ha_green = hc > ho
    ha_red = hc < ho
    
    mac_bull = (m > 0) & (hist > 0) & (df["close"] > ema200)
    mac_bear = (m < 0) & (hist < 0) & (df["close"] < ema200)
    
    buy_cond = ha_red.shift(1) & ha_green & mac_bull
    sell_cond = ha_green.shift(1) & ha_red & mac_bear
    
    return ind.sig_from(buy_cond, sell_cond)
