# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_339", "strategy/s20.339/strategy20_339.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_751", "strategy/s20.751/strategy20_751.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {
    "sid": "20.758",
    "name": "S20.339 x S20.751 (CONFIRM w5)",
    "concept": "Inside Bar Breakout (A) confirmed by Mixed Curvature+Rainbow (B)",
    "logic": "A (Inside Bar Breakout) ให้จุดเข้าระเบิดกรอบ, B (Quadratic Curvature + Rainbow MA) เป็นตัวยืนยันจังหวะเริ่มกลับตัวและโมเมนตัมที่เข้ามาในช่วงไม่เกิน 5 แท่ง เพื่อป้องกันการ Breakout หลอกในจังหวะที่แรงส่งเริ่มสวนทาง",
    "parents": ["20.339", "20.751"],
    "mix": "CONFIRM",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = mod_a.generate(df, tf)
    sig_b = mod_b.generate(df, tf)
    
    final_sig = np.zeros_like(sig_a)
    w = 5
    
    # Precompute rolling signals for B
    b_buy_recent = pd.Series(sig_b == 1).rolling(window=w, min_periods=1).max().astype(bool).values
    b_sell_recent = pd.Series(sig_b == -1).rolling(window=w, min_periods=1).max().astype(bool).values
    
    buy_cond = (sig_a == 1) & b_buy_recent
    sell_cond = (sig_a == -1) & b_sell_recent
    
    final_sig[buy_cond] = 1
    final_sig[sell_cond] = -1
    
    return final_sig
