# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.355",
    "name": "ADX Exhaustion Reversal",
    "concept": "เข้าเทรดสวนเทรนด์เมื่อเทรนด์เก่ารุนแรงมากจนหมดแรง (Exhaustion) โดยดูจาก ADX ที่ขึ้นสุดแล้วหักหัวลง พร้อมกับราคาตัด EMA 20",
    "logic": "ADX > 40 หมายถึงเทรนด์รุนแรงมาก (Overextended) เมื่อ ADX เริ่มหักหัวลงแสดงว่าเทรนด์นั้นเสียโมเมนตัม หากราคาตัดกลับข้าม EMA 20 ได้จะเป็นจุดยืนยันการกลับตัวหรือพักตัวลึก, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    pdi, ndi, adx = ind.dmi(df, 14)
    ema20 = ind.ema(df["close"], 20)
    
    adx_exhaust = (adx.shift(1) > 40.0) & (adx < adx.shift(1))
    
    buy_cond = adx_exhaust & (ndi > pdi) & ind.cross_up(df["close"], ema20)
    sell_cond = adx_exhaust & (pdi > ndi) & ind.cross_dn(df["close"], ema20)
    
    return ind.sig_from(buy_cond, sell_cond)
