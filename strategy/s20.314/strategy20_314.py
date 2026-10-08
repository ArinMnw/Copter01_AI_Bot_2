# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {'sid': '20.314', 'name': 'Heikin-Ashi Parabolic SAR Flip', 'concept': 'Calculate PSAR on smoothed Heikin-Ashi candles to filter out noise on flip', 'logic': 'HA reduces noise, making PSAR trend flips more reliable and less prone to whipsaws', 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 25, 'be_r': 1.0}

def generate(df, tf):
    ho, hh, hl, hc = I.heikin_ashi(df)
    ha_df = pd.DataFrame({'open': ho, 'high': hh, 'low': hl, 'close': hc, 'time': df['time']}, index=df.index)
    sar, tr = I.psar(ha_df)
    
    buy = (tr == 1) & (tr.shift(1) == -1)
    sell = (tr == -1) & (tr.shift(1) == 1)
    
    return I.sig_from(buy, sell)
