# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.407",
    "name": "Stochastic DMI Sync Reversal",
    "concept": "เข้าเทรดตอนที่ Stochastic ตัดขึ้นในโซน Oversold พร้อมกับทิศทางหลักจาก DMI ชี้ขึ้น",
    "logic": "เช็คเทรนด์ด้วย DMI (+DI > -DI สำหรับ Buy) และมี ADX > 20 เพื่อยืนยันว่ามีแนวโน้มชัดเจน จากนั้นหาจุดเข้าตอนย่อตัวโดยใช้ Stochastic < 20 และ K ตัด D ขึ้น",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    pdi, ndi, adx = ind.dmi(df, 14)
    kk, dd = ind.stoch(df, 14, 3, 3)

    # Buy: +DI > -DI, ADX > 20, Stoch อยู่โซนต่ำ (<20) และตัดขึ้น
    buy_cond1 = pdi > ndi
    buy_cond2 = adx > 20
    buy_cond3 = kk < 20
    buy_cond4 = ind.cross_up(kk, dd)
    buy_signal = buy_cond1 & buy_cond2 & buy_cond3 & buy_cond4

    # Sell: -DI > +DI, ADX > 20, Stoch อยู่โซนสูง (>80) และตัดลง
    sell_cond1 = ndi > pdi
    sell_cond2 = adx > 20
    sell_cond3 = kk > 80
    sell_cond4 = ind.cross_dn(kk, dd)
    sell_signal = sell_cond1 & sell_cond2 & sell_cond3 & sell_cond4

    return ind.sig_from(buy_signal, sell_signal)
