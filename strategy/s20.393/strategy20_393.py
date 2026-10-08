# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.393",
    "name": "PSAR Bullish DMI Sync",
    "concept": "เข้าเทรดด้วยการตัดกันของ DMI ในขณะที่โครงสร้างราคาเทรนด์ย่อยยังคงถูกประคองไว้ด้วย Parabolic SAR",
    "logic": "PSAR ทำหน้าที่บอกทิศทางของเทรนด์ย่อยที่กำลังดำเนินอยู่ หากเกิดสัญญาณ PDI ตัด NDI ขึ้นในขณะที่จุด PSAR อยู่ด้านล่าง (Bullish) หมายความว่าแรงซื้อได้กลับมาเอาชนะแรงขายโดยสมบูรณ์ในการย่อตัวรอบนั้น, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sar, sar_dir = ind.psar(df, 0.02, 0.2)
    pdi, ndi, adx = ind.dmi(df, 14)
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = (sar_dir > 0.0) & ind.cross_up(pdi, ndi) & (df["close"] > ema200)
    sell_cond = (sar_dir < 0.0) & ind.cross_dn(pdi, ndi) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
