# -*- coding: utf-8 -*-
"""S20.306 — Keltner Channel Momentum Breakout

แนวคิด: ราคาทะลุกรอบ Keltner Channel ออกไปพร้อมกับ RSI ยืนยัน Momentum (>55 สำหรับขาขึ้น, <45 สำหรับขาลง)
Causal: ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น engine จะเข้าไม้ที่ราคาเปิดของแท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import pandas as pd
import ind as I

META = {
    'sid': '20.306',
    'name': 'Keltner Channel Momentum Breakout',
    'concept': 'Close ทะลุ Keltner Channel บน (BUY) หรือล่าง (SELL) ร่วมกับ RSI บ่งชี้โมเมนตัมทิศทางเดียวกัน',
    'sl_atr': 2.0,
    'rr': 1.5,
    'max_hold': 48,
    'be_r': 0.8
}

def generate(df, tf):
    kc_lower, _, kc_upper = I.keltner(df, n=20, k=2.0)
    rsi = I.rsi(df["close"], n=14)
    
    buy = I.cross_up(df["close"], kc_upper) & (rsi > 55)
    sell = I.cross_dn(df["close"], kc_lower) & (rsi < 45)
    
    return I.sig_from(buy, sell)
