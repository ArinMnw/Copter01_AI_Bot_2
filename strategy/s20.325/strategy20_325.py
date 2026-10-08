# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.325",
    "name": "RSI SMA Momentum Ignition",
    "concept": "ใช้ RSI ตัดขึ้นเหนือเส้น SMA ของตัวเองเพื่อจับจังหวะที่โมเมนตัมเริ่มเร่งตัวขึ้นในทิศทางของเทรนด์หลัก",
    "logic": "RSI ตัดเส้นค่าเฉลี่ยตัวเองเป็น Leading Indicator ของโมเมนตัมที่กำลังมา, ยืนยันเทรนด์ด้วย SMA200 เพื่อลด False Signal, SL 1.5 ATR ปกป้องหลอก, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    rsi = ind.rsi(df["close"], 14)
    rsi_sma = ind.sma(rsi, 20)
    sma200 = ind.sma(df["close"], 200)
    
    close = df["close"]
    
    # Uptrend
    uptrend = close > sma200
    buy_cond = uptrend & ind.cross_up(rsi, rsi_sma)
    
    # Downtrend
    downtrend = close < sma200
    sell_cond = downtrend & ind.cross_dn(rsi, rsi_sma)
    
    return ind.sig_from(buy_cond, sell_cond)
