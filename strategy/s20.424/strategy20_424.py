# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.424",
    "name": "Heikin Ashi WMA Pullback",
    "concept": "หาจังหวะย่อตัวในเทรนด์ขาขึ้นโดยใช้ Heikin Ashi ยืนยันแนวโน้มหลักร่วมกับ Stochastic",
    "logic": "เช็คเทรนด์หลักว่า Heikin Ashi เป็นสีเขียว 2 แท่งติดกันและอยู่เหนือ WMA 50 หากราคาแท่งเทียนปกติย่อลงมาใต้ WMA 20 และ Stochastic ตวัดขึ้น จะเข้า Buy (Sell ตรงข้าม)",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    hao, hah, hal, hac = ind.heikin_ashi(df)
    wma20 = ind.wma(df["close"], 20)
    wma50 = ind.wma(df["close"], 50)
    kk, dd = ind.stoch(df, 14, 3, 3)

    # Heikin Ashi เป็นสีเขียว 2 แท่งติด
    ha_bull = (hac > hao) & (hac.shift(1) > hao.shift(1))
    ha_bear = (hac < hao) & (hac.shift(1) < hao.shift(1))

    # Buy: HA เป็นขาขึ้น และอยู่เหนือ WMA 50 แต่ราคาปกติย่อลงมาต่ำกว่า WMA 20 แล้ว Stochastic ตวัดขึ้น
    buy_cond1 = ha_bull & (hac > wma50)
    buy_cond2 = df["close"] < wma20
    buy_cond3 = ind.cross_up(kk, dd)
    buy_signal = buy_cond1 & buy_cond2 & buy_cond3

    # Sell: HA เป็นขาลง และอยู่ใต้ WMA 50 แต่ราคาปกติเด้งขึ้นมาสูงกว่า WMA 20 แล้ว Stochastic ตวัดลง
    sell_cond1 = ha_bear & (hac < wma50)
    sell_cond2 = df["close"] > wma20
    sell_cond3 = ind.cross_dn(kk, dd)
    sell_signal = sell_cond1 & sell_cond2 & sell_cond3

    return ind.sig_from(buy_signal, sell_signal)
