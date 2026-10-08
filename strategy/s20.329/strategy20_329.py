# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.329",
    "name": "PSAR HMA Trend Alignment",
    "concept": "เข้าเทรดเมื่อ Parabolic SAR กลับตัว (Flip) และได้รับการยืนยันทิศทางจากเส้น HMA สองเส้นที่ตัดกันแล้ว",
    "logic": "PSAR มีจุดอ่อนเมื่อตลาดแกว่ง การใช้ HMA (Hull MA) ซึ่งไวและสมูทมาช่วยกรอง จะทำให้เทรดเฉพาะ PSAR Flip ที่เกิดในทิศทางของโมเมนตัมหลัก, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sar, tr = ind.psar(df)
    hma14 = ind.hma(df["close"], 14)
    hma50 = ind.hma(df["close"], 50)
    
    # PSAR Flip
    psar_buy = (tr == 1) & (tr.shift(1) == -1)
    psar_sell = (tr == -1) & (tr.shift(1) == 1)
    
    # HMA Alignment
    hma_bull = hma14 > hma50
    hma_bear = hma14 < hma50
    
    buy_cond = psar_buy & hma_bull
    sell_cond = psar_sell & hma_bear
    
    return ind.sig_from(buy_cond, sell_cond)
