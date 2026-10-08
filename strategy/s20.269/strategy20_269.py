# -*- coding: utf-8 -*-
"""S20.269 — Prior-Close Magnet Reversion

แนวคิด: ราคาวิ่งห่าง close ของงวดก่อน (วัน/สัปดาห์/เดือนตาม TF) > 2.5 ATR แล้วเกิดแท่งกลับทิศที่ปิดเกินครึ่งแท่งก่อนหน้า → เข้าสวนกลับหา prior close
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.269', 'name': 'Prior-Close Magnet Reversion', 'concept': 'ราคาวิ่งห่าง close ของงวดก่อน (วัน/สัปดาห์/เดือนตาม TF) > 2.5 ATR แล้วเกิดแท่งกลับทิศที่ปิดเกินครึ่งแท่งก่อนหน้า → เข้าสวนกลับหา prior close', 'sl_atr': 1.2, 'rr': 1.2, 'max_hold': 16}


def generate(df, tf):
    key = I.period_key(df, tf)
    _, _, pc, _ = I.prev_period_hl(df, key)
    o, c = df["open"], df["close"]
    a = I.atr(df, 14)
    mid_prev = (df["open"].shift(1) + df["close"].shift(1)) / 2
    return I.sig_from((pc - c > 2.5 * a) & (c > o) & (c > mid_prev), (c - pc > 2.5 * a) & (c < o) & (c < mid_prev))
