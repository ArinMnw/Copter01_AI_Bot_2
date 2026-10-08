# -*- coding: utf-8 -*-
"""S20.308 — Chandelier Exit Trend Reversal

แนวคิด: Chandelier Exit ใช้คำนวณจุดตัดขาดทุน (Trailing Stop) จากจุดสูงสุด/ต่ำสุด
เมื่อราคาวิ่งทะลุเส้น Chandelier ของฝั่งตรงข้าม แปลว่าเกิดการเปลี่ยนเทรนด์ (Trend Reversal)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {
    'sid': '20.308',
    'name': 'Chandelier Exit Trend Reversal',
    'concept': 'เมื่อราคา Close ตัดเส้น Chandelier ฝั่งตรงข้าม (Highest - 3ATR หรือ Lowest + 3ATR) เป็นสัญญาณเปลี่ยนเทรนด์ (Reversal)',
    'logic': 'Trend Following ระยะกลาง-ยาว ตามการเหวี่ยงตัว (3ATR) ใช้ RR กว้าง (2.5) และทนถือข้ามวัน (48 แท่ง)',
    'sl_atr': 3.0,
    'rr': 2.5,
    'max_hold': 48,
    'be_r': 1.5
}

def generate(df, tf):
    atr22 = I.atr(df, 22)
    
    # ถ้าเทรนด์เดิมเป็นขาลง จุดเปลี่ยนเป็นขาขึ้น (Short Stop) คือ Lowest + 3*ATR
    short_stop = I.lowest(df["low"], 22) + 3.0 * atr22
    buy = I.cross_up(df["close"], short_stop)
    
    # ถ้าเทรนด์เดิมเป็นขาขึ้น จุดเปลี่ยนเป็นขาลง (Long Stop) คือ Highest - 3*ATR
    long_stop = I.highest(df["high"], 22) - 3.0 * atr22
    sell = I.cross_dn(df["close"], long_stop)
    
    return I.sig_from(buy, sell)
