# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.373",
    "name": "EMA Golden Cross Trend",
    "concept": "เข้าเทรดด้วยสัญญาณคลาสสิก Golden/Death Cross ของ EMA 20/50 แต่กรองเฉพาะจังหวะที่เกิดเหนือเส้นเทรนด์หลัก EMA 200",
    "logic": "Golden Cross ปกติมักจะช้าและเจอ False Signal บ่อยเมื่อเกิดในกรอบ Sideway หรือขัดแย้งกับเทรนด์ใหญ่ การบังคับให้ EMA 50 > EMA 200 และราคา > EMA 200 จะช่วยรับประกันว่าจุดตัดนี้เป็นเพียงจุดเริ่มต้นของการเร่งตัวตามเทรนด์เดิม, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    ema20 = ind.ema(df["close"], 20)
    ema50 = ind.ema(df["close"], 50)
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = ind.cross_up(ema20, ema50) & (df["close"] > ema200) & (ema50 > ema200)
    sell_cond = ind.cross_dn(ema20, ema50) & (df["close"] < ema200) & (ema50 < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
