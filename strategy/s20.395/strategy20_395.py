# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.395",
    "name": "TTM Squeeze ADX Breakout",
    "concept": "เข้าเทรดตอนที่ตลาดเพิ่งหลุดจากสภาวะสะสมพลัง (Squeeze) โดยมี ADX ช่วยกรองทิศทางว่าเป็นเทรนด์จริงไม่ใช่ False Break",
    "logic": "การที่ Bollinger Bands เข้ามาอยู่ข้างใน Keltner Channel (Squeeze) แปลว่าตลาดบีบตัวถึงขีดสุด เมื่อราคา Breakout ออกจาก Bollinger Bands พร้อมกับ ADX > 25 จะทำให้มีความน่าจะเป็นสูงมากที่กราฟจะระเบิดเป็นเทรนด์ใหญ่, กรองทิศทางด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    bl, bm, bu = ind.bbands(df["close"], n=20, k=2.0)
    kl, km, ku = ind.keltner(df, n=20, k=1.5, atr_n=20)
    pdi, ndi, adx = ind.dmi(df, 14)
    ema200 = ind.ema(df["close"], 200)
    
    squeeze = (bu < ku) & (bl > kl)
    
    buy_cond = ind.cross_up(df["close"], bu) & squeeze.shift(1) & (adx > 25.0) & (df["close"] > ema200)
    sell_cond = ind.cross_dn(df["close"], bl) & squeeze.shift(1) & (adx > 25.0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
