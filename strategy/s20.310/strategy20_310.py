# -*- coding: utf-8 -*-
"""S20.310 — Hull MACD (HMACD) Momentum Cross

แนวคิด: ใช้ Hull Moving Average (HMA) แทน EMA ในการคำนวณ MACD (12, 26, 9) เพื่อลดความล่าช้า (Lag) 
เข้าเทรดเมื่อเส้น HMACD ตัดเส้น Signal (HMA9) จากโซนที่ต่ำกว่า 0 (BUY) หรือสูงกว่า 0 (SELL)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {
    'sid': '20.310',
    'name': 'Hull MACD (HMACD) Momentum Cross',
    'concept': 'คำนวณ MACD ด้วย HMA(12)-HMA(26) และเส้น Signal คือ HMA(9) เข้า Buy เมื่อตัดขึ้นใต้ศูนย์ Sell เมื่อตัดลงเหนือศูนย์ (จับจุดกลับตัวไว)',
    'logic': 'Mean Reversion ระยะสั้น-กลาง อาศัยความไวของ HMA SL(1.5) RR(1.5) ถือครองไม่เกิน 16 แท่ง',
    'sl_atr': 1.5,
    'rr': 1.5,
    'max_hold': 16,
    'be_r': 1.0
}

def generate(df, tf):
    h12 = I.hma(df["close"], 12)
    h26 = I.hma(df["close"], 26)
    hmacd = h12 - h26
    signal = I.hma(hmacd, 9)
    
    buy = I.cross_up(hmacd, signal) & (hmacd < 0)
    sell = I.cross_dn(hmacd, signal) & (hmacd > 0)
    
    return I.sig_from(buy, sell)
