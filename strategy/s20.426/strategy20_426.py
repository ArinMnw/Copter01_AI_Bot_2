# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.426",
    "name": "Triple WMA Volatility Expansion",
    "concept": "เข้าเทรดในช่วงที่มีการขยายตัวของความผันผวนพร้อมไปกับเทรนด์แข็งแกร่ง (Triple WMA)",
    "logic": "เช็คความผันผวนที่เพิ่มขึ้นจากความกว้างของ Bollinger Bands ร่วมกับเทรนด์ของ WMA 3 เส้น และจังหวะที่ราคาตัดเส้น WMA 20 พร้อม MACD สนับสนุน",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    wma20 = ind.wma(df["close"], 20)
    wma50 = ind.wma(df["close"], 50)
    wma100 = ind.wma(df["close"], 100)
    bbl, bbm, bbu = ind.bbands(df["close"], 20, 2.0)
    macd, macdsig, macdhist = ind.macd(df["close"], 12, 26, 9)

    bb_width = bbu - bbl
    bb_expanding = bb_width > bb_width.shift(1)

    buy_cond1 = (wma20 > wma50) & (wma50 > wma100)
    buy_cond2 = macdhist > 0
    buy_cond3 = bb_expanding
    buy_cond4 = ind.cross_up(df["close"], wma20)
    buy_signal = buy_cond1 & buy_cond2 & buy_cond3 & buy_cond4

    sell_cond1 = (wma20 < wma50) & (wma50 < wma100)
    sell_cond2 = macdhist < 0
    sell_cond3 = bb_expanding
    sell_cond4 = ind.cross_dn(df["close"], wma20)
    sell_signal = sell_cond1 & sell_cond2 & sell_cond3 & sell_cond4

    return ind.sig_from(buy_signal, sell_signal)
