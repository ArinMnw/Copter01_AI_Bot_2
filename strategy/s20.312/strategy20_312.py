# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.312', 'name': 'Triple EMA Alignment RSI Pullback', 'concept': 'Trend alignment of EMA20 > 50 > 200 with RSI(14) pullback below 40 for BUY, vice versa for SELL', 'logic': 'RSI dip allows entering strong EMA trend at better price', 'sl_atr': 1.5, 'rr': 2.0, 'max_hold': 30, 'be_r': 1.0}

def generate(df, tf):
    e20 = I.ema(df["close"], 20)
    e50 = I.ema(df["close"], 50)
    e200 = I.ema(df["close"], 200)
    r = I.rsi(df["close"], 14)
    
    uptrend = (e20 > e50) & (e50 > e200)
    downtrend = (e20 < e50) & (e50 < e200)
    
    buy = uptrend & (r < 40) & (r.shift(1) >= 40)
    sell = downtrend & (r > 60) & (r.shift(1) <= 60)
    
    return I.sig_from(buy, sell)
