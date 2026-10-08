# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind

META = {
    "sid": "20.316",
    "name": "Heikin-Ashi DMI Trend Alignment",
    "concept": "ใช้ Heikin-Ashi ลด noise แล้วคำนวณ DMI/ADX เพื่อยืนยันความแข็งแกร่งของเทรนด์",
    "logic": "HA กรอง noise ยิบย่อย, ADX > 25 ยืนยันเทรนด์ชัดเจน, SL 2.0 ATR ให้พื้นที่หายใจเผื่อ false breakout ตอนแรก, RR 1.5 เน้นเก็บกำไรในเทรนด์ย่อย, ถือ 36 แท่งเผื่อให้เทรนด์พัฒนาเต็มที่",
    "sl_atr": 2.0,
    "rr": 1.5,
    "max_hold": 36,
    "be_r": 1.0
}

def generate(df, tf):
    ho, hh, hl, hc = ind.heikin_ashi(df)
    ha_df = pd.DataFrame({"open": ho, "high": hh, "low": hl, "close": hc, "time": df["time"]}, index=df.index)
    
    pdi, ndi, adx = ind.dmi(ha_df, 14)
    rsi = ind.rsi(ha_df["close"], 14)
    
    trend_strong = adx > 25
    buy_cond = trend_strong & (pdi > ndi) & (hc > ho) & (rsi > 50) & ind.cross_up(pdi, ndi)
    sell_cond = trend_strong & (ndi > pdi) & (hc < ho) & (rsi < 50) & ind.cross_up(ndi, pdi)
    
    return ind.sig_from(buy_cond, sell_cond)
