# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.384",
    "name": "RSI Bollinger Breakout",
    "concept": "เข้าเทรดเมื่อ RSI เกิดการทะลุกรอบ Bollinger Bands ของตัวมันเอง ซึ่งบ่งบอกถึงโมเมนตัมที่ผิดปกติ",
    "logic": "แทนที่จะใช้ค่า RSI แบบคงที่ (Overbought/Oversold) การนำ Bollinger Bands มาครอบบน RSI จะช่วยปรับระดับตามความผันผวนของรอบนั้น หาก RSI ตัดเส้นกรอบบน (Upper Band) แสดงว่าเกิดโมเมนตัมพุ่งแรงจนมีนัยสำคัญ, กรองด้วย EMA 200, SL 1.5 ATR, RR 1.5, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    rsi = ind.rsi(df["close"], 14)
    # ครอบ Bollinger Bands ลงบน RSI
    bl, bm, bu = ind.bbands(rsi, n=20, k=2.0)
    ema200 = ind.ema(df["close"], 200)
    
    buy_cond = ind.cross_up(rsi, bu) & (df["close"] > ema200)
    sell_cond = ind.cross_dn(rsi, bl) & (df["close"] < ema200)
    
    return ind.sig_from(buy_cond, sell_cond)
