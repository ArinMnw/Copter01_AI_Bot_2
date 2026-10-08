# -*- coding: utf-8 -*-
"""S20.181 — Narrow CPR (Central Pivot Range) Breakout

แนวคิด: Central Pivot Range จาก HLC งวดก่อน (Pivot, BC, TC): ถ้า CPR แคบ (<25% ของ ATR เฉลี่ยของงวด) = วันเทรนด์ รอราคาปิดทะลุ TC/BC ครั้งแรกของงวด → เข้าตามทิศ
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.181', 'name': 'Narrow CPR (Central Pivot Range) Breakout', 'concept': 'Central Pivot Range จาก HLC งวดก่อน (Pivot, BC, TC): ถ้า CPR แคบ (<25% ของ ATR เฉลี่ยของงวด) = วันเทรนด์ รอราคาปิดทะลุ TC/BC ครั้งแรกของงวด → เข้าตามทิศ', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 24}


def generate(df, tf):
    key = I.period_key(df, tf)
    ph, pl, pc, _ = I.prev_period_hl(df, key)
    p = (ph + pl + pc) / 3; bc = (ph + pl) / 2; tc = 2 * p - bc
    top, bot = np.maximum(tc, bc), np.minimum(tc, bc)
    narrow = (top - bot) < 0.25 * (ph - pl) * 0.5
    c = df["close"]
    up = narrow & (c > top); dn = narrow & (c < bot)
    fu = up & (up.astype(int).groupby(key).cumsum() == 1); fd = dn & (dn.astype(int).groupby(key).cumsum() == 1)
    return I.sig_from(fu & (c.shift(1) <= top), fd & (c.shift(1) >= bot))
