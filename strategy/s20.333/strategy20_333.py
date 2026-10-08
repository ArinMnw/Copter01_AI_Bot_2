# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.333",
    "name": "Daily Key Level Rejection",
    "concept": "เทรดเด้งกลับเมื่อราคาทดสอบจุดสูงสุด/ต่ำสุดของวันก่อนหน้า (Daily High/Low) แล้วเกิดการปฏิเสธราคา",
    "logic": "ระดับราคา H/L ของวันก่อนหน้าเป็นแนวรับแนวต้านสำคัญทางจิตวิทยา หากราคาทะลุไปแล้วดึงกลับ (False Breakout) ในทิศทางเดียวกับ EMA200 มักจะเป็นจุดกลับตัวที่แม่นยำ, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    dh, dl, dc, do = ind.prev_period_hl(df, ind.day_key(df))
    ema200 = ind.ema(df["close"], 200)
    
    # Buy: price dips below previous day's low but closes above it, making a bullish candle
    buy_cond = (df["low"] <= dl) & (df["close"] > dl) & (df["close"] > df["open"]) & (df["close"] > ema200)
    
    # Sell: price spikes above previous day's high but closes below it, making a bearish candle
    sell_cond = (df["high"] >= dh) & (df["close"] < dh) & (df["close"] < df["open"]) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
