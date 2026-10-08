# -*- coding: utf-8 -*-
"""S20.249 — LBR Momentum Pinball

แนวคิด: Linda Raschke Momentum Pinball: RSI(3) ของ ROC 1 แท่ง ต่ำกว่า 30 (โมเมนตัมสั้นถูกขายเกิน) ในขณะที่ราคาเหนือ EMA50 → BUY แท่งถัดไป; > 70 และใต้ EMA50 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.249', 'name': 'LBR Momentum Pinball', 'concept': 'Linda Raschke Momentum Pinball: RSI(3) ของ ROC 1 แท่ง ต่ำกว่า 30 (โมเมนตัมสั้นถูกขายเกิน) ในขณะที่ราคาเหนือ EMA50 → BUY แท่งถัดไป; > 70 และใต้ EMA50 → SELL', 'sl_atr': 1.2, 'rr': 1.5, 'max_hold': 12}


def generate(df, tf):
    roc1 = df["close"].diff()
    r = I.rsi(roc1, 3)
    e = I.ema(df["close"], 50)
    return I.sig_from((r < 30) & (r.shift(1) >= 30) & (df["close"] > e), (r > 70) & (r.shift(1) <= 70) & (df["close"] < e))
