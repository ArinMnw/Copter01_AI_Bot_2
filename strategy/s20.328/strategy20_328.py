# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.328",
    "name": "Doji Keltner Breakout",
    "concept": "หาแท่งเทียน Doji ที่เกิดใน Keltner Channel เพื่อเข้าเทรดเมื่อมีการ Breakout ทะลุ High/Low ของ Doji",
    "logic": "Doji สะท้อนความลังเลของตลาด การ Breakout จาก Doji พร้อมยืนยันด้วยเทรนด์ (EMA50) จะเป็นจุดเริ่มต้นการเคลื่อนไหวใหม่, SL 1.5 ATR ปกป้องหลอก, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    kl, km, ku = ind.keltner(df, n=20, k=2.0, atr_n=14)
    ema50 = ind.ema(df["close"], 50)
    
    op = df["open"]
    hi = df["high"]
    lo = df["low"]
    cl = df["close"]
    
    rng = hi - lo
    body = (cl - op).abs()
    
    # Doji condition: body is very small compared to range
    is_doji = (body <= 0.15 * rng) & (rng > ind.atr(df, 14) * 0.2)
    
    # Doji must be inside Keltner
    doji_inside = is_doji & (hi < ku) & (lo > kl)
    
    # We want to buy if current bar breaks doji's high
    # So previous bar was doji inside, and now price > doji's high
    prev_doji = doji_inside.shift(1)
    break_up = prev_doji & (df["close"] > df["high"].shift(1)) & (df["close"] > ema50)
    break_dn = prev_doji & (df["close"] < df["low"].shift(1)) & (df["close"] < ema50)
    
    return ind.sig_from(break_up, break_dn)
