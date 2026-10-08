# -*- coding: utf-8 -*-
"""S20.296 — DecisionPoint Price Momentum Oscillator Cross

แนวคิด: PMO (Carl Swenlin): ROC1 smooth ด้วย custom EMA 35 แล้ว 20 (×10) ตัด signal EMA10 ขึ้นขณะ PMO < 0 → BUY; ตัดลงขณะ PMO > 0 → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.296', 'name': 'DecisionPoint Price Momentum Oscillator Cross', 'concept': 'PMO (Carl Swenlin): ROC1 smooth ด้วย custom EMA 35 แล้ว 20 (×10) ตัด signal EMA10 ขึ้นขณะ PMO < 0 → BUY; ตัดลงขณะ PMO > 0 → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    roc = 100 * df["close"].pct_change()
    cema = lambda x, n: x.ewm(alpha=2 / n, adjust=False).mean()
    pmo = cema(10 * cema(roc, 35), 20)
    sg = I.ema(pmo, 10)
    w = pd.Series(np.arange(len(df)) > 100, index=df.index)
    return I.sig_from(I.cross_up(pmo, sg) & (pmo < 0) & w, I.cross_dn(pmo, sg) & (pmo > 0) & w)
