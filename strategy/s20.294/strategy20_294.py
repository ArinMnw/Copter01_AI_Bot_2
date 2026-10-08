# -*- coding: utf-8 -*-
"""S20.294 — Higher-Period Pivot Regime Cross

แนวคิด: Pivot ของงวดที่ใหญ่กว่า 1 ขั้น (TF≤H1 ใช้ pivot สัปดาห์ก่อน, H4 ใช้ ~เดือน, D1 ใช้ ~ไตรมาส): ราคาปิดข้าม P ขึ้นหลังอยู่ใต้ P ≥ 10 แท่ง และ open งวดปัจจุบันอยู่ใต้ P (เปลี่ยน regime ภายในงวด) → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.294', 'name': 'Higher-Period Pivot Regime Cross', 'concept': 'Pivot ของงวดที่ใหญ่กว่า 1 ขั้น (TF≤H1 ใช้ pivot สัปดาห์ก่อน, H4 ใช้ ~เดือน, D1 ใช้ ~ไตรมาส): ราคาปิดข้าม P ขึ้นหลังอยู่ใต้ P ≥ 10 แท่ง และ open งวดปัจจุบันอยู่ใต้ P (เปลี่ยน regime ภายในงวด) → BUY; กลับด้าน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    wk = I.week_key(df)
    key = wk if tf in ("M1", "M5", "M15", "M30", "H1") else ((wk // 4) if tf == "H4" else (wk // 13)).astype(np.int64)
    ph, pl, pc, _ = I.prev_period_hl(df, key)
    p = (ph + pl + pc) / 3
    _, _, po = I.period_running(df, key)
    c = df["close"]
    below = (c.shift(1) < p.shift(1)).rolling(10).sum() == 10
    above = (c.shift(1) > p.shift(1)).rolling(10).sum() == 10
    return I.sig_from(below & (c > p) & (po < p), above & (c < p) & (po > p))
