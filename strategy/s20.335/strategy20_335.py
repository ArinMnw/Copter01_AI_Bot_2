# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.335",
    "name": "Bollinger Volatility Expansion Breakout",
    "concept": "เทรดตามการระเบิดของราคาโดยใช้ความกว้างของ Bollinger Bands (BB Width) ที่ขยายตัวอย่างฉับพลัน",
    "logic": "เมื่อ BB Width มีค่า Z-Score เกิน 2.0 แสดงว่าตลาดมีความผันผวนสูงมาก (Volatility Expansion) การทะลุขอบบน/ล่างพร้อมกับเทรนด์ EMA200 จะบอกทิศทางการระเบิด, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    bl, bm, bu = ind.bbands(df["close"], n=20, k=2.0)
    ema200 = ind.ema(df["close"], 200)
    
    bb_width = (bu - bl) / bm
    bb_width_z = ind.zscore(bb_width, 50)
    
    vol_expansion = bb_width_z > 2.0
    
    buy_cond = vol_expansion & (df["close"] > bu) & (df["close"] > ema200)
    sell_cond = vol_expansion & (df["close"] < bl) & (df["close"] < ema200)
    
    # Ensure it's a breakout, not just hovering
    buy_sig = ind.cross_up(df["close"], bu) & buy_cond
    sell_sig = ind.cross_dn(df["close"], bl) & sell_cond
    
    return ind.sig_from(buy_sig, sell_sig)
