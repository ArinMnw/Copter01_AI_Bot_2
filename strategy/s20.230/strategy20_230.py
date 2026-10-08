# -*- coding: utf-8 -*-
"""S20.230 — ATR Renko Two-Brick Reversal

แนวคิด: สร้าง Renko แบบ causal ขนาดอิฐ = ATR14 (freeze ต่อวัน): หลังอิฐแดง ≥ 3 ก้อน เกิดอิฐเขียวกลับตัว 2 ก้อน (reversal ต้องวิ่ง 2 อิฐ) → BUY; กลับด้าน → SELL
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.230', 'name': 'ATR Renko Two-Brick Reversal', 'concept': 'สร้าง Renko แบบ causal ขนาดอิฐ = ATR14 (freeze ต่อวัน): หลังอิฐแดง ≥ 3 ก้อน เกิดอิฐเขียวกลับตัว 2 ก้อน (reversal ต้องวิ่ง 2 อิฐ) → BUY; กลับด้าน → SELL', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30}


def generate(df, tf):
    c = df["close"].to_numpy()
    a = I.atr(df, 14).to_numpy()
    day = (df["time"] // 86400).to_numpy()
    n = len(c); sig = np.zeros(n, dtype=np.int8)
    base = np.nan; box = np.nan; dirs = []; cur_day = None
    for i in range(n):
        if not np.isfinite(a[i]):
            continue
        if day[i] != cur_day:
            cur_day, box = day[i], a[i]
        if not np.isfinite(base):
            base = c[i]; continue
        new = []
        last = dirs[-1] if dirs else 0
        while True:
            if last >= 0 and c[i] >= base + box:
                base += box; new.append(1); last = 1
            elif last <= 0 and c[i] <= base - box:
                base -= box; new.append(-1); last = -1
            elif last == 1 and c[i] <= base - 2 * box:
                base -= 2 * box; new.append(-1); new.append(-1); last = -1
            elif last == -1 and c[i] >= base + 2 * box:
                base += 2 * box; new.append(1); new.append(1); last = 1
            else:
                break
        if new:
            prev = dirs[-3:] if len(dirs) >= 3 else []
            if len(prev) == 3 and all(x == -1 for x in prev) and new[0] == 1 and len(new) >= 2:
                sig[i] = 1
            elif len(prev) == 3 and all(x == 1 for x in prev) and new[0] == -1 and len(new) >= 2:
                sig[i] = -1
            dirs.extend(new)
            dirs = dirs[-10:]
    return sig
