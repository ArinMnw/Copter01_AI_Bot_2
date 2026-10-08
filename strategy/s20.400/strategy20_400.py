# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.400",
    "name": "MACD Hist RSI 50 Breakout",
    "concept": "เข้าเทรดเมื่อ MACD เปลี่ยนโมเมนตัมเป็นบวกในขณะที่ RSI เพิ่งตัดเข้าสู่โซน Bullish อ่อนๆ (50-60)",
    "logic": "การที่ MACD Histogram ตัด 0 ขึ้นแสดงถึงแรงส่งใหม่กำลังก่อตัว หากจังหวะนั้น RSI อยู่ในช่วง 50-60 แปลว่าเทรนด์เพิ่งเริ่ม ไม่ Overbought เกินไป จึงเป็นจุดเข้าที่ได้เปรียบทั้งความสดใหม่ของเทรนด์และช่องว่างในการทำกำไร, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    m, sig, hist = ind.macd(df["close"])
    rsi = ind.rsi(df["close"], 14)
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = ind.cross_up(hist, 0.0) & (rsi > 50.0) & (rsi < 60.0) & (df["close"] > ema200)
    sell_cond = ind.cross_dn(hist, 0.0) & (rsi < 50.0) & (rsi > 40.0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
