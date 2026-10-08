# -*- coding: utf-8 -*-
"""S20.197 — Detrended Price Oscillator Cycle Turn (causal)

แนวคิด: DPO แบบ causal: close − SMA20 ที่ถูกเลื่อน (n/2+1) แท่ง (ใช้ค่าอดีตเท่านั้น) ทำ cycle low (< −1 ATR) แล้วหันขึ้น 2 แท่ง → BUY; cycle high หันลง → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.197', 'name': 'Detrended Price Oscillator Cycle Turn (causal)', 'concept': 'DPO แบบ causal: close − SMA20 ที่ถูกเลื่อน (n/2+1) แท่ง (ใช้ค่าอดีตเท่านั้น) ทำ cycle low (< −1 ATR) แล้วหันขึ้น 2 แท่ง → BUY; cycle high หันลง → SELL', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 20}


def generate(df, tf):
    c = df["close"]
    dpo = c - I.sma(c, 20).shift(11)
    a = I.atr(df, 14)
    lo = dpo.shift(2) < -a; hi = dpo.shift(2) > a
    return I.sig_from(lo & (dpo > dpo.shift(1)) & (dpo.shift(1) > dpo.shift(2)), hi & (dpo < dpo.shift(1)) & (dpo.shift(1) < dpo.shift(2)))
