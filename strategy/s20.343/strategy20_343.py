# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.343",
    "name": "HMA Bollinger Extreme Fade",
    "concept": "เทรดสวน (Mean Reversion) เมื่อเส้น Hull MA อ่อนตัวกลับเข้ามาในกรอบ Bollinger Bands (k=2.5) ในช่วงตลาดไม่มีเทรนด์แรง",
    "logic": "HMA มีความไวสูง เมื่อ HMA ทะลุขอบ BB (2.5 SD) แสดงว่าราคา Overextended มาก หาก HMA ตัดกลับเข้ามาแสดงว่าโมเมนตัมหมดแรงและกำลังกลับตัว, กรองด้วย ADX < 30, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    bl, bm, bu = ind.bbands(df["close"], n=20, k=2.5)
    hma14 = ind.hma(df["close"], 14)
    pdi, ndi, adx = ind.dmi(df, 14)
    
    flat_market = adx < 30
    
    # Buy when HMA crosses back inside from below the lower band
    buy_cond = ind.cross_up(hma14, bl) & flat_market
    
    # Sell when HMA crosses back inside from above the upper band
    sell_cond = ind.cross_dn(hma14, bu) & flat_market
    
    return ind.sig_from(buy_cond, sell_cond)
