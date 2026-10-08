# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.417",
    "name": "Stochastic RSI Re-entry",
    "concept": "เข้าเทรดเมื่อราคาย่อตัวในแนวโน้มใหญ่ (WMA100) โดยดูจาก Stochastic ตัดขึ้นร่วมกับ RSI สนับสนุนแนวโน้ม",
    "logic": "เช็คแนวโน้มหลักจาก WMA 100 และทิศทางกลางจาก RSI (>50 เป็นบวก, <50 เป็นลบ) จากนั้นหาจังหวะที่ราคาย่อจน Stochastic เข้าโซน Oversold/Overbought แล้วหักหัวกลับ",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    wma100 = ind.wma(df["close"], 100)
    rsi = ind.rsi(df["close"], 14)
    kk, dd = ind.stoch(df, 14, 3, 3)

    # Buy: ราคา > WMA100, RSI > 50, และ Stoch %K ตัด %D ขึ้นหลังจากลงต่ำกว่า 20
    buy_trend = (df["close"] > wma100) & (rsi > 50)
    buy_entry = (kk.shift(1) < 20) & ind.cross_up(kk, dd)
    buy_signal = buy_trend & buy_entry

    # Sell: ราคา < WMA100, RSI < 50, และ Stoch %K ตัด %D ลงหลังจากขึ้นสูงกว่า 80
    sell_trend = (df["close"] < wma100) & (rsi < 50)
    sell_entry = (kk.shift(1) > 80) & ind.cross_dn(kk, dd)
    sell_signal = sell_trend & sell_entry

    return ind.sig_from(buy_signal, sell_signal)
