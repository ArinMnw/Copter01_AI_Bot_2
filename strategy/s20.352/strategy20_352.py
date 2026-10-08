# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.352",
    "name": "PSAR MACD Alignment Breakout",
    "concept": "เข้าเทรดเมื่อเทรนด์กลับทิศ (PSAR Flip) โดยมีโมเมนตัมจาก MACD Histogram สอดคล้องในทิศทางเดียวกัน",
    "logic": "PSAR ใช้ดักจับจุดเริ่มต้นเทรนด์ใหม่ หากสอดคล้องกับโมเมนตัมของ MACD (Histogram อยู่ในแดนบวก/ลบ) และเทรนด์ใหญ่ EMA200 โอกาสเป็นเทรนด์จริงจะสูงขึ้น, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sar, sar_dir = ind.psar(df, 0.02, 0.2)
    m, sig, hist = ind.macd(df["close"])
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = ind.cross_up(sar_dir, 0.0) & (hist > 0) & (df["close"] > ema200)
    sell_cond = ind.cross_dn(sar_dir, 0.0) & (hist < 0) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
