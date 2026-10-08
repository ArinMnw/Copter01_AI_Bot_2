# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.406",
    "name": "MACD Hist Zero Cross Pullback",
    "concept": "เข้าเทรดเมื่อ MACD Histogram ตัด 0 แล้วย่อตัวลงมาแต่ไม่หลุด",
    "logic": "ใช้ MACD Histogram เพื่อหาจังหวะที่แรงส่งเริ่มเปลี่ยนฝั่ง แล้วรอการย่อตัว (Pullback) ของ Histogram เพื่อเป็นการยืนยัน และเทรดตามทิศทางของ EMA 50 และ RSI",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    ema50 = ind.ema(df["close"], 50)
    macd, macdsignal, macdhist = ind.macd(df["close"], 12, 26, 9)
    rsi = ind.rsi(df["close"], 14)

    buy_cond1 = macdhist > 0
    buy_cond2 = macdhist < macdhist.shift(1)
    buy_cond3 = df["close"] > ema50
    buy_cond4 = rsi > 50

    buy_signal = buy_cond1 & buy_cond2 & buy_cond3 & buy_cond4

    sell_cond1 = macdhist < 0
    sell_cond2 = macdhist > macdhist.shift(1)
    sell_cond3 = df["close"] < ema50
    sell_cond4 = rsi < 50

    sell_signal = sell_cond1 & sell_cond2 & sell_cond3 & sell_cond4

    return ind.sig_from(buy_signal, sell_signal)
