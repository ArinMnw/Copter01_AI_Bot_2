# -*- coding: utf-8 -*-
"""S20.307 — Synthetic VIX (Williams Vix Fix) Extreme Reversion

แนวคิด: คำนวณ WVF สำหรับขาขึ้น (fear peak) และ Inverse WVF สำหรับขาลง (euphoria peak)
เมื่อ VIX ทะลุขอบบน Bollinger Bands (20, 2.0) ขึ้นไปและตัดลง (peak recession) -> BUY/SELL
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {
    'sid': '20.307',
    'name': 'Synthetic VIX Extreme Reversion',
    'concept': 'คำนวณ WVF และ Inverse WVF (22) หากวิ่งทะลุกรอบบนของ BB(20, 2.0) แล้ววกกลับตัดลงมา ให้เข้าเทรดทิศทางตรงข้าม',
    'logic': 'ดัก Reversion จาก Fear/Greed extreme SL ไม่กว้างมาก (1.5) และเป้า RR 2.0 เวลาพักตัว 24 แท่ง',
    'sl_atr': 1.5,
    'rr': 2.0,
    'max_hold': 24,
    'be_r': 1.0
}

def generate(df, tf):
    # WVF (Williams Vix Fix) = (Highest(Close, 22) - Low) / Highest(Close, 22) * 100
    hh22 = I.highest(df["close"], 22)
    wvf = (hh22 - df["low"]) / hh22 * 100
    _, _, wvf_upper = I.bbands(wvf, 20, 2.0)
    
    # Inverse WVF for Tops
    ll22 = I.lowest(df["close"], 22)
    iwvf = (df["high"] - ll22) / ll22 * 100
    _, _, iwvf_upper = I.bbands(iwvf, 20, 2.0)
    
    buy = I.cross_dn(wvf, wvf_upper)
    sell = I.cross_dn(iwvf, iwvf_upper)
    
    return I.sig_from(buy, sell)
