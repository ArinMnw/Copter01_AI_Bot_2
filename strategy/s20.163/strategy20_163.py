# -*- coding: utf-8 -*-
"""S20.163 — Schaff Trend Cycle 25/75 Cross

แนวคิด: Schaff Trend Cycle (MACD 23/50 ผ่าน stochastic 2 ชั้น cycle 10): STC ตัดขึ้นเหนือ 25 → BUY, ตัดลงใต้ 75 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.163', 'name': 'Schaff Trend Cycle 25/75 Cross', 'concept': 'Schaff Trend Cycle (MACD 23/50 ผ่าน stochastic 2 ชั้น cycle 10): STC ตัดขึ้นเหนือ 25 → BUY, ตัดลงใต้ 75 → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    m = I.ema(df["close"], 23) - I.ema(df["close"], 50)
    def stoch_s(x, n=10):
        lo, hi = x.rolling(n).min(), x.rolling(n).max()
        return (100 * (x - lo) / (hi - lo).replace(0, np.nan)).ffill()
    k1 = stoch_s(m).ewm(alpha=0.5, adjust=False).mean()
    stc = stoch_s(k1).ewm(alpha=0.5, adjust=False).mean()
    return I.sig_from(I.cross_up(stc, 25), I.cross_dn(stc, 75))
