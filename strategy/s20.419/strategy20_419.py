# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.419",
    "name": "PSAR Volatility ADX Breakout",
    "concept": "เข้าเทรดเมื่อราคาทะลุกรอบความผันผวนพร้อมแรงส่งจาก ADX ในทิศทางของ PSAR",
    "logic": "เช็คเทรนด์หลักด้วย PSAR หากราคาพุ่งทะลุกรอบขอบบนของ Keltner พร้อมกับ ADX > 25 และ +DI > -DI ถือเป็นสัญญาณระเบิดแรงส่ง (Buy), ทางตรงข้ามเป็น Sell",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sar, sar_trend = ind.psar(df, 0.02, 0.2)
    pdi, ndi, adx = ind.dmi(df, 14)
    kl, km, ku = ind.keltner(df, 20, 1.5)

    buy_cond1 = sar_trend == 1
    buy_cond2 = (adx > 25) & (pdi > ndi)
    buy_cond3 = ind.cross_up(df["close"], ku)
    buy_signal = buy_cond1 & buy_cond2 & buy_cond3

    sell_cond1 = sar_trend == -1
    sell_cond2 = (adx > 25) & (ndi > pdi)
    sell_cond3 = ind.cross_dn(df["close"], kl)
    sell_signal = sell_cond1 & sell_cond2 & sell_cond3

    return ind.sig_from(buy_signal, sell_signal)
