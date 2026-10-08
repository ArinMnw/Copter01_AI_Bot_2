# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.413",
    "name": "HMA Turnaround EMA200",
    "concept": "เข้าเทรดเมื่อ HMA วกกลับตัวไปในทิศทางเดียวกับเทรนด์หลัก (EMA 200)",
    "logic": "ใช้ความไวของ HMA ในการจับจุดกลับตัว โดยรอให้ HMA พลิกหัวขึ้น/ลง และยืนยันแนวโน้มใหญ่ด้วยราคาที่อยู่เหนือ/ใต้ EMA 200",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    hma50 = ind.hma(df["close"], 50)
    ema200 = ind.ema(df["close"], 200)

    # Buy: HMA 50 เพิ่งวกหัวกลับขึ้น (แท่งปัจจุบัน > แท่งก่อน และแท่งก่อน < แท่งก่อนหน้า)
    hma_turn_up = (hma50 > hma50.shift(1)) & (hma50.shift(1) < hma50.shift(2))
    buy_signal = hma_turn_up & (df["close"] > ema200)

    # Sell: HMA 50 เพิ่งวกหัวกลับลง (แท่งปัจจุบัน < แท่งก่อน และแท่งก่อน > แท่งก่อนหน้า)
    hma_turn_dn = (hma50 < hma50.shift(1)) & (hma50.shift(1) > hma50.shift(2))
    sell_signal = hma_turn_dn & (df["close"] < ema200)

    return ind.sig_from(buy_signal, sell_signal)
