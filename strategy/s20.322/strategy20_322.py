# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.322",
    "name": "RSI Simple Divergence Reversal",
    "concept": "หารอบการกลับตัวจากการเกิด Divergence อย่างง่าย โดยเทียบราคาสูงสุด/ต่ำสุดใหม่ กับแรงส่ง RSI ที่ลดลง",
    "logic": "ราคาทำ High/Low ใหม่ในรอบ 20 แท่ง แต่ RSI ไม่ทำนิวไฮ/โลว์ และเกิดแท่งเทียนกลับตัว (สีตรงข้าม) เป็นสัญญาณหมดแรง, SL 1.5 ATR ปกป้อง, RR 1.5 หวังผลดีดกลับระยะสั้น, ถือ 24 แท่ง",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    rsi = ind.rsi(df["close"], 14)
    
    hh20 = ind.highest(df["high"], 20)
    ll20 = ind.lowest(df["low"], 20)
    
    # We use shift(1) for comparing past RSI to avoid current bar changing
    # Max RSI of the past 10 bars, excluding the current bar
    max_rsi_past = ind.highest(rsi.shift(1), 10)
    min_rsi_past = ind.lowest(rsi.shift(1), 10)
    
    # Sell condition: New 20-bar high, but RSI is lower than the past max RSI by at least 5 points
    bearish_div = (df["high"] >= hh20) & (rsi < max_rsi_past - 5) & (df["close"] < df["open"])
    
    # Buy condition: New 20-bar low, but RSI is higher than the past min RSI by at least 5 points
    bullish_div = (df["low"] <= ll20) & (rsi > min_rsi_past + 5) & (df["close"] > df["open"])
    
    return ind.sig_from(bullish_div, bearish_div)
