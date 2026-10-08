# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.330",
    "name": "Stochastic RSI Trend Filter",
    "concept": "ใช้ Stochastic RSI ที่ตอบสนองไวกว่า RSI ธรรมดา เพื่อจับจังหวะ Pullback ในเทรนด์หลัก",
    "logic": "StochRSI มีความอ่อนไหวต่อโมเมนตัมมากกว่า จึงจับรอบการแกว่งในเทรนด์ได้คมขึ้น กรองด้วย EMA 50/200 เพื่อเทรดเฉพาะหน้าเทรนด์, SL 1.5 ATR, RR 1.5 หวังผลระยะสั้น, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    rsi = ind.rsi(df["close"], 14)
    df_rsi = pd.DataFrame({"low": rsi, "high": rsi, "close": rsi}, index=df.index)
    
    # Stochastic of RSI
    k, d = ind.stoch(df_rsi, 14, 3, 3)
    
    ema50 = ind.ema(df["close"], 50)
    ema200 = ind.ema(df["close"], 200)
    
    # Uptrend
    uptrend = ema50 > ema200
    buy_cond = uptrend & ind.cross_up(k, d) & (k < 20)
    
    # Downtrend
    downtrend = ema50 < ema200
    sell_cond = downtrend & ind.cross_dn(k, d) & (k > 80)
    
    return ind.sig_from(buy_cond, sell_cond)
