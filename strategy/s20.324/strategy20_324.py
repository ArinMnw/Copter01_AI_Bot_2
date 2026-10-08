# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.324",
    "name": "Keltner Extreme Pin Bar Fade",
    "concept": "หาแท่งเทียน Pin Bar (Hammer/Shooting Star) ที่เกิดนอก Keltner Channel เพื่อเข้าเทรดสวนกลับเข้าสู่เส้นค่าเฉลี่ย",
    "logic": "Pin Bar นอก Keltner แสดงถึงการปฏิเสธราคา (Price Rejection) อย่างรุนแรงในโซน Extreme, SL 1.5 ATR ปกป้องหลอก, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    kl, km, ku = ind.keltner(df, n=20, k=2.0, atr_n=14)
    atr = ind.atr(df, 14)
    sma200 = ind.sma(df["close"], 200)
    
    op = df["open"]
    hi = df["high"]
    lo = df["low"]
    cl = df["close"]
    
    rng = hi - lo
    body = (cl - op).abs()
    top_body = pd.concat([op, cl], axis=1).max(axis=1)
    bot_body = pd.concat([op, cl], axis=1).min(axis=1)
    
    top_tail = hi - top_body
    bot_tail = bot_body - lo
    
    valid_size = rng > (atr * 0.5)
    
    hammer = valid_size & (bot_tail > 2 * body) & (top_tail < 0.5 * body)
    shooting_star = valid_size & (top_tail > 2 * body) & (bot_tail < 0.5 * body)
    
    buy_cond = hammer & (lo < kl) & (cl > sma200)
    sell_cond = shooting_star & (hi > ku) & (cl < sma200)
    
    return ind.sig_from(buy_cond, sell_cond)
