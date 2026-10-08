# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.388",
    "name": "EMA 50 Trend Pullback",
    "concept": "เข้าเทรดเมื่อราคาย่อตัวลึกจนหลุดเส้น EMA 50 แล้วพลิกกลับมายืนเหนือเส้นได้ในเทรนด์ขาขึ้นที่ชัดเจน",
    "logic": "ในขณะที่ EMA เรียงตัวแบบกระทิง (20 > 50 > 200) การที่ราคาย่อหลุด EMA 50 แปลว่าตลาดย่อลึก (Deep Pullback) การรอให้ราคากลับมายืนเหนือ EMA 50 ได้อีกครั้งคือการยืนยันว่าแรงขายหมดแล้วและพร้อมวิ่งตามเทรนด์เดิม, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    ema20 = ind.ema(df["close"], 20)
    ema50 = ind.ema(df["close"], 50)
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = ind.cross_up(df["close"], ema50) & (ema20 > ema50) & (ema50 > ema200)
    sell_cond = ind.cross_dn(df["close"], ema50) & (ema20 < ema50) & (ema50 < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
