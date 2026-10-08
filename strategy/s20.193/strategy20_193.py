# -*- coding: utf-8 -*-
"""S20.193 — Wilder Accumulative Swing Index Breakout

แนวคิด: Welles Wilder Accumulative Swing Index: ASI ทะลุ high สูงสุด 30 แท่งก่อนหน้า (swing breakout ใน space ของ ASI) พร้อมราคาปิดเหนือ EMA20 → BUY; ทะลุ low → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.193', 'name': 'Wilder Accumulative Swing Index Breakout', 'concept': 'Welles Wilder Accumulative Swing Index: ASI ทะลุ high สูงสุด 30 แท่งก่อนหน้า (swing breakout ใน space ของ ASI) พร้อมราคาปิดเหนือ EMA20 → BUY; ทะลุ low → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    pc, po = c.shift(1), o.shift(1)
    k = pd.concat([(h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    a1, a2, a3 = (h - pc).abs(), (l - pc).abs(), h - l
    r = np.where((a1 >= a2) & (a1 >= a3), a1 - 0.5 * a2 + 0.25 * (pc - po).abs(),
         np.where((a2 >= a1) & (a2 >= a3), a2 - 0.5 * a1 + 0.25 * (pc - po).abs(), a3 + 0.25 * (pc - po).abs()))
    T = I.atr(df, 14) * 3
    si = 50 * ((c - pc) + 0.5 * (c - o) + 0.25 * (pc - po)) / pd.Series(r, index=df.index).replace(0, np.nan) * (k / T)
    asi = si.fillna(0).cumsum()
    e20 = I.ema(c, 20)
    return I.sig_from((asi > I.highest(asi, 30).shift(1)) & (asi.shift(1) <= I.highest(asi, 30).shift(2)) & (c > e20),
                      (asi < I.lowest(asi, 30).shift(1)) & (asi.shift(1) >= I.lowest(asi, 30).shift(2)) & (c < e20))
