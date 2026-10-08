# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.332",
    "name": "ADX Trend Ignition with PSAR",
    "concept": "เข้าเทรด ณ จุดเริ่มต้นของเทรนด์แข็งแกร่ง (ADX ตัด 25 ขึ้นไป) โดยมี Parabolic SAR ยืนยันทิศทาง",
    "logic": "ADX ตัด 25 เป็นสัญญาณบอกว่าตลาดเริ่มมีเทรนด์ที่ชัดเจน การให้ PSAR ยืนยันช่วยป้องกันการเข้าผิดทางในช่วงที่ ADX เพิ่งเริ่มยกตัว, SL 1.5 ATR, RR 1.5, ถือ 36 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 36,
    "be_r": 1.0
}

def generate(df, tf):
    pdi, ndi, adx = ind.dmi(df, 14)
    sar, tr = ind.psar(df)
    
    adx_break = ind.cross_up(adx, 25.0)
    
    buy_cond = adx_break & (pdi > ndi) & (tr == 1)
    sell_cond = adx_break & (ndi > pdi) & (tr == -1)
    
    return ind.sig_from(buy_cond, sell_cond)
