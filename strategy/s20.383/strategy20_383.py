# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.383",
    "name": "ADX Exhaustion V-Reversal",
    "concept": "เข้าเทรดสวนกลับอย่างฉับพลันในขณะที่ ADX มีค่าสูงมาก (เทรนด์ก่อนหน้าหมดแรงและเกิดการกลับตัว V-Shape)",
    "logic": "ADX > 40 บ่งบอกว่าเทรนด์ก่อนหน้านั้นไปสุดทางจนใกล้ Exhaustion ถ้าจู่ๆ PDI ตัด NDI ขึ้นในสภาวะนี้ แปลว่าเกิดการสวนกลับที่รุนแรงมาก (V-Shape) หากเทรดไปในทิศทางเดียวกับ EMA 200 จะเป็นการรับมีดที่กลายเป็นจุดเริ่มต้นเวฟใหม่ที่แม่นยำมาก, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    pdi, ndi, adx = ind.dmi(df, 14)
    ema200 = ind.ema(df["close"], 200)
    
    exhaustion = adx > 40.0
    
    buy_cond = exhaustion & ind.cross_up(pdi, ndi) & (df["close"] > ema200)
    sell_cond = exhaustion & ind.cross_up(ndi, pdi) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
