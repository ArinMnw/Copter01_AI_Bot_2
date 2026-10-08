# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.414",
    "name": "Triple WMA DMI Pullback",
    "concept": "เทรดตามเทรนด์ด้วย Triple WMA พร้อมจังหวะย่อตัวและยืนยันด้วย DMI",
    "logic": "เช็คเทรนด์หลักด้วย WMA 20, 50, 100 แบบเรียงตัว และมี ADX > 25 หนุนหลัง หาจังหวะเข้าเทรดเมื่อราคาย่อตัวตัด WMA 20 และ RSI ยังสนับสนุนทิศทาง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    wma20 = ind.wma(df["close"], 20)
    wma50 = ind.wma(df["close"], 50)
    wma100 = ind.wma(df["close"], 100)
    pdi, ndi, adx = ind.dmi(df, 14)
    rsi = ind.rsi(df["close"], 14)

    buy_trend = (wma20 > wma50) & (wma50 > wma100) & (pdi > ndi) & (adx > 25)
    buy_pullback = df["close"] < wma20
    buy_confirm = rsi > 40
    buy_signal = buy_trend & buy_pullback & buy_confirm

    sell_trend = (wma20 < wma50) & (wma50 < wma100) & (ndi > pdi) & (adx > 25)
    sell_pullback = df["close"] > wma20
    sell_confirm = rsi < 60
    sell_signal = sell_trend & sell_pullback & sell_confirm

    return ind.sig_from(buy_signal, sell_signal)
