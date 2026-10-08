# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.369",
    "name": "Triple EMA RSI Re-entry",
    "concept": "เข้าเทรดจังหวะย่อแล้วเด้งกลับข้ามเส้น EMA 20 ในขณะที่เทรนด์หลัก (EMA 50, 200) สนับสนุนอย่างเต็มที่",
    "logic": "การที่ราคาข้าม EMA 20 กลับขึ้นมาได้ในขณะที่ EMA เรียงตัวเป็นขาขึ้น (20>50>200) และ RSI มีโมเมนตัมพุ่งกลับมาเกิน 50 เป็นการหาจังหวะ Re-entry ตามเทรนด์แบบอนุรักษ์นิยมและมีประสิทธิภาพ, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    ema20 = ind.ema(df["close"], 20)
    ema50 = ind.ema(df["close"], 50)
    ema200 = ind.ema(df["close"], 200)
    rsi = ind.rsi(df["close"], 14)
    
    uptrend = (ema20 > ema50) & (ema50 > ema200)
    downtrend = (ema20 < ema50) & (ema50 < ema200)
    
    buy_cond = ind.cross_up(df["close"], ema20) & uptrend & (rsi > 50.0) & (rsi > rsi.shift(1))
    sell_cond = ind.cross_dn(df["close"], ema20) & downtrend & (rsi < 50.0) & (rsi < rsi.shift(1))
    
    return ind.sig_from(buy_cond, sell_cond)
