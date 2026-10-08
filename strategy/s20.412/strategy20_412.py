# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.412",
    "name": "Volatility Explosion MACD",
    "concept": "เข้าเทรดในช่วงที่ความผันผวนสูง (BB ถ่างกว่า Keltner) ตามเทรนด์หลัก (EMA200)",
    "logic": "ใช้จังหวะที่ Bollinger Bands ถ่างออกกว้างกว่า Keltner Channel บ่งบอกถึงแรงระเบิดของราคา โดยเทรดตามเทรนด์ EMA 200 และมี MACD Histogram ยืนยัน Momentum",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    ema200 = ind.ema(df["close"], 200)
    bbl, bbm, bbu = ind.bbands(df["close"], 20, 2.0)
    kl, km, ku = ind.keltner(df, 20, 1.5)
    macd, macdsig, macdhist = ind.macd(df["close"], 12, 26, 9)

    bb_width = bbu - bbl
    keltner_width = ku - kl

    is_explosion = bb_width > keltner_width

    # Buy: อยู่เหนือ EMA 200, ระเบิดออก, และ MACD Histogram เป็นบวกและกำลังเพิ่มขึ้น
    buy_cond1 = df["close"] > ema200
    buy_cond2 = is_explosion
    buy_cond3 = (macdhist > 0) & (macdhist > macdhist.shift(1))
    buy_signal = buy_cond1 & buy_cond2 & buy_cond3

    # Sell: อยู่ใต้ EMA 200, ระเบิดออก, และ MACD Histogram เป็นลบและกำลังลดลง
    sell_cond1 = df["close"] < ema200
    sell_cond2 = is_explosion
    sell_cond3 = (macdhist < 0) & (macdhist < macdhist.shift(1))
    sell_signal = sell_cond1 & sell_cond2 & sell_cond3

    return ind.sig_from(buy_signal, sell_signal)
