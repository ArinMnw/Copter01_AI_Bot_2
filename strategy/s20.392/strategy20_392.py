# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.392",
    "name": "PSAR Bullish RSI Dip",
    "concept": "เข้าเทรดเมื่อราคาย่อตัวในระยะสั้น (RSI Dip) แต่โครงสร้างหลักยังคงถูกประคองไว้ด้วย Parabolic SAR",
    "logic": "PSAR มีหน้าที่เป็น Trailing Support ถ้าราคาย่อตัวลงมาจน RSI ลงไปลึกกว่า 40 แล้วตัดกลับขึ้นมาได้ในขณะที่จุด PSAR ยังคงอยู่ด้านล่าง (Bullish) หมายความว่าแนวรับสำคัญยังทำงานได้ดี นี่คือจุดเข้า Pullback ที่เสี่ยงต่ำ, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sar, sar_dir = ind.psar(df, 0.02, 0.2)
    rsi = ind.rsi(df["close"], 14)
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = (sar_dir > 0.0) & ind.cross_up(rsi, 40.0) & (df["close"] > ema200)
    sell_cond = (sar_dir < 0.0) & ind.cross_dn(rsi, 60.0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
