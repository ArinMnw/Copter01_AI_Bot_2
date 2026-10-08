# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.408",
    "name": "Triple EMA Pullback Stoch",
    "concept": "เข้าเทรดจังหวะย่อตัวในเทรนด์ชัดเจนด้วย Stochastic ควบคู่กับ Triple EMA",
    "logic": "เช็คเทรนด์หลักด้วย EMA 20, 50, 100 เรียงตัวกัน และหาจุดเข้าเมื่อราคาย่อมาต่ำกว่า EMA 20 โดยมี Stochastic Oversold/Overbought เป็นจุดยืนยัน",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    ema20 = ind.ema(df["close"], 20)
    ema50 = ind.ema(df["close"], 50)
    ema100 = ind.ema(df["close"], 100)
    macd, macdsig, macdhist = ind.macd(df["close"], 12, 26, 9)
    kk, dd = ind.stoch(df, 14, 3, 3)

    # Buy: เทรนด์ขึ้นชัดเจน, ราคาย่อลงมาต่ำกว่า EMA 20 แต่ MACD ยังเป็นบวก และ Stochastic เด้งขึ้นจาก Oversold
    buy_trend = (ema20 > ema50) & (ema50 > ema100)
    buy_pullback = df["close"] < ema20
    buy_confirm = (macd > 0) & (kk < 30) & ind.cross_up(kk, dd)
    buy_signal = buy_trend & buy_pullback & buy_confirm

    # Sell: เทรนด์ลงชัดเจน, ราคาย่อขึ้นไปสูงกว่า EMA 20 แต่ MACD ยังเป็นลบ และ Stochastic หักลงจาก Overbought
    sell_trend = (ema20 < ema50) & (ema50 < ema100)
    sell_pullback = df["close"] > ema20
    sell_confirm = (macd < 0) & (kk > 70) & ind.cross_dn(kk, dd)
    sell_signal = sell_trend & sell_pullback & sell_confirm

    return ind.sig_from(buy_signal, sell_signal)
