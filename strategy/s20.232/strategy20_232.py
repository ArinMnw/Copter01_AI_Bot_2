# -*- coding: utf-8 -*-
"""S20.232 — Point & Figure Double-Top Breakout

แนวคิด: Point & Figure แบบ causal (box = 0.5·ATR14 freeze ต่อวัน, reversal 3 box): คอลัมน์ X ใหม่ทะลุยอดคอลัมน์ X ก่อนหน้า (double-top buy) → BUY; คอลัมน์ O ทะลุก้น O ก่อน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.232', 'name': 'Point & Figure Double-Top Breakout', 'concept': 'Point & Figure แบบ causal (box = 0.5·ATR14 freeze ต่อวัน, reversal 3 box): คอลัมน์ X ใหม่ทะลุยอดคอลัมน์ X ก่อนหน้า (double-top buy) → BUY; คอลัมน์ O ทะลุก้น O ก่อน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    h = df["high"].to_numpy(); l = df["low"].to_numpy()
    a = I.atr(df, 14).to_numpy(); day = (df["time"] // 86400).to_numpy()
    n = len(h); sig = np.zeros(n, dtype=np.int8)
    col_dir = 0; col_top = col_bot = np.nan; prev_x_top = prev_o_bot = np.nan; box = np.nan; cur = None; fired = False
    for i in range(n):
        if not np.isfinite(a[i]):
            continue
        if day[i] != cur:
            cur, box = day[i], 0.5 * a[i]
        if col_dir == 0:
            col_dir, col_top, col_bot = 1, h[i], l[i]; continue
        if col_dir == 1:
            if h[i] > col_top:
                col_top = h[i]
                if not fired and np.isfinite(prev_x_top) and col_top > prev_x_top + box:
                    sig[i] = 1; fired = True
            elif l[i] < col_top - 3 * box:
                prev_x_top = col_top; col_dir, col_bot, fired = -1, l[i], False
        else:
            if l[i] < col_bot:
                col_bot = l[i]
                if not fired and np.isfinite(prev_o_bot) and col_bot < prev_o_bot - box:
                    sig[i] = -1; fired = True
            elif h[i] > col_bot + 3 * box:
                prev_o_bot = col_bot; col_dir, col_top, fired = 1, h[i], False
    return sig
