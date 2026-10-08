# -*- coding: utf-8 -*-
"""S20.256 — Harami Exhaustion after Extended Run

แนวคิด: Harami: แท่งยาว (body > 1.5 ATR) ตามทิศ trend ที่วิ่งมาแล้ว ≥ 3 ATR ใน 10 แท่ง ตามด้วยแท่งเล็กสีตรงข้ามที่อยู่ในเนื้อแท่งแม่ → เข้าสวน (แรงหมด)
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.256', 'name': 'Harami Exhaustion after Extended Run', 'concept': 'Harami: แท่งยาว (body > 1.5 ATR) ตามทิศ trend ที่วิ่งมาแล้ว ≥ 3 ATR ใน 10 แท่ง ตามด้วยแท่งเล็กสีตรงข้ามที่อยู่ในเนื้อแท่งแม่ → เข้าสวน (แรงหมด)', 'sl_atr': 1.2, 'rr': 1.5, 'max_hold': 16}


def generate(df, tf):
    o, c = df["open"], df["close"]
    a = I.atr(df, 14)
    b1 = (c.shift(1) - o.shift(1))
    top1 = pd.concat([o.shift(1), c.shift(1)], axis=1).max(axis=1); bot1 = pd.concat([o.shift(1), c.shift(1)], axis=1).min(axis=1)
    inside = (pd.concat([o, c], axis=1).max(axis=1) < top1) & (pd.concat([o, c], axis=1).min(axis=1) > bot1)
    run_up = (c.shift(1) - c.shift(11)) > 3 * a; run_dn = (c.shift(11) - c.shift(1)) > 3 * a
    return I.sig_from(inside & (b1 < -1.5 * a) & run_dn & (c > o), inside & (b1 > 1.5 * a) & run_up & (c < o))
