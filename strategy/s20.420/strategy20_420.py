# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.420",
    "name": "HMA RSI Squeeze Out",
    "concept": "เข้าเทรดในช่วงเริ่มหลุดกรอบ Squeeze โดยใช้ HMA เพื่อลดสัญญาณหลอกและ RSI ยืนยัน Momentum",
    "logic": "เช็ค Squeeze (Bollinger ถ่างน้อยกว่า Keltner) จากนั้นหาทิศทางเบรกเอาท์ด้วย HMA 20 ตัด 50 และต้องมี RSI ไปในทิศทางเดียวกัน (>50 หรือ <50)",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    bbl, bbm, bbu = ind.bbands(df["close"], 20, 2.0)
    kl, km, ku = ind.keltner(df, 20, 1.5)
    hma20 = ind.hma(df["close"], 20)
    hma50 = ind.hma(df["close"], 50)
    rsi = ind.rsi(df["close"], 14)

    is_squeeze = (bbu < ku) & (bbl > kl)
    was_squeeze = is_squeeze.rolling(3).max() > 0

    # Buy: เพิ่งมี Squeeze, HMA 20 > HMA 50 (บอกเทรนด์สั้นไปกลาง), RSI > 50
    buy_cond1 = was_squeeze
    buy_cond2 = hma20 > hma50
    buy_cond3 = rsi > 50
    buy_signal = buy_cond1 & buy_cond2 & buy_cond3

    # Sell: เพิ่งมี Squeeze, HMA 20 < HMA 50, RSI < 50
    sell_cond1 = was_squeeze
    sell_cond2 = hma20 < hma50
    sell_cond3 = rsi < 50
    sell_signal = sell_cond1 & sell_cond2 & sell_cond3

    return ind.sig_from(buy_signal, sell_signal)
