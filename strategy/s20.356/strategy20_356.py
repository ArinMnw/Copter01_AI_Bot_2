# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.356",
    "name": "Bollinger Volatility Z-Score Breakout",
    "concept": "เข้าเทรดเมื่อความกว้างของ Bollinger Bands (Volatility) ขยายตัวรุนแรงผิดปกติ (Z-Score > 2.0) พร้อมกับราคาเบรคกรอบ",
    "logic": "BB Width ที่ขยายตัวเฉียบพลันมักเป็นจุดเริ่มต้นของเทรนด์ใหญ่ การใช้ Z-Score มาจับจะช่วยให้เจาะจงเฉพาะจังหวะที่ขยายตัวผิดปกติทางสถิติจริงๆ กรองทิศทางด้วยขอบ BB และ EMA200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    bl, bm, bu = ind.bbands(df["close"], n=20, k=2.0)
    bb_width = (bu - bl) / bm.replace(0, np.nan)
    bbw_z = ind.zscore(bb_width, 50)
    
    ema200 = ind.ema(df["close"], 200)
    
    # ความผันผวนขยายตัวผิดปกติ
    vol_break = ind.cross_up(bbw_z, 2.0)
    
    buy_cond = vol_break & (df["close"] > bu) & (df["close"] > ema200)
    sell_cond = vol_break & (df["close"] < bl) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
