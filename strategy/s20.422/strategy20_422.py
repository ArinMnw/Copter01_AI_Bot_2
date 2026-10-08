# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.422",
    "name": "Triple MA Volatility Breakout",
    "concept": "เทรดเมื่อราคาทะลุกรอบความผันผวนพร้อมแรงส่งจาก ADX ในเทรนด์หลักที่แข็งแกร่ง",
    "logic": "เช็คเทรนด์หลักจากเส้นค่าเฉลี่ย 3 รูปแบบ (HMA 20 > EMA 50 > WMA 100) และรอจังหวะที่ราคาเบรก Bollinger Band พร้อมกับ ADX แสดงแรงส่งในทิศทางนั้น",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    hma20 = ind.hma(df["close"], 20)
    ema50 = ind.ema(df["close"], 50)
    wma100 = ind.wma(df["close"], 100)
    pdi, ndi, adx = ind.dmi(df, 14)
    bbl, bbm, bbu = ind.bbands(df["close"], 20, 2.0)

    buy_trend = (hma20 > ema50) & (ema50 > wma100)
    buy_cond2 = (adx > 25) & (pdi > ndi)
    buy_cond3 = ind.cross_up(df["close"], bbu)
    buy_signal = buy_trend & buy_cond2 & buy_cond3

    sell_trend = (hma20 < ema50) & (ema50 < wma100)
    sell_cond2 = (adx > 25) & (ndi > pdi)
    sell_cond3 = ind.cross_dn(df["close"], bbl)
    sell_signal = sell_trend & sell_cond2 & sell_cond3

    return ind.sig_from(buy_signal, sell_signal)
