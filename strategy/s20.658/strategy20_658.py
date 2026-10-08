# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_168", "strategy/s20.168/strategy20_168.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

META = {
    "sid": "20.658",
    "name": "S20.168 x S20.277 (FILTER)",
    "concept": "Ehlers Crossover (A) filtered by Quadratic Curvature State (B)",
    "logic": "S20.168 provides Ehlers Super Smoother Crossover signals. We FILTER these trend initiations using the continuous state of S20.277 (Quadratic Regression Curvature). We only enter the trend crossover if the 30-bar macro quadratic curvature is strictly concave-up (cs > 0) and the slope is positive (ss > 0). This ensures we only trade crossovers that are supported by the underlying nonlinear macro market structure.",
    "parents": ["20.168", "20.277"],
    "mix": "FILTER",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}

def generate(df, tf):
    sig_a = mod_a.generate(df, tf)
    
    # Calculate B continuous state (Quad Reg)
    c = df["close"].to_numpy()
    n = 30
    m = len(c)
    x = np.arange(n, dtype=float)
    A = np.vstack([x ** 2, x, np.ones(n)]).T
    P = np.linalg.pinv(A)
    cur = np.full(m, np.nan)
    slp = np.full(m, np.nan)
    
    for i in range(n - 1, m):
        a2, b1, _ = P @ c[i - n + 1:i + 1]
        cur[i] = a2
        slp[i] = 2 * a2 * (n - 1) + b1
        
    cs = pd.Series(cur, index=df.index)
    ss = pd.Series(slp, index=df.index)
    
    buy_a = sig_a == 1
    sell_a = sig_a == -1
    
    # B state
    state_b_up = (cs > 0) & (ss > 0)
    state_b_dn = (cs < 0) & (ss < 0)
    
    buy = buy_a & state_b_up
    sell = sell_a & state_b_dn
    
    return ind.sig_from(pd.Series(buy), pd.Series(sell))
