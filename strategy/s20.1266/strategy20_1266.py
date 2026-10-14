# -*- coding: utf-8 -*-
"""Causal parent mixing; execution is provided by the shared engine."""
import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd

META = {'sid': '20.1266', 'name': 'CMO Histogram x ABC Defense', 'concept': 'CONFIRM of two existing causal parent generators', 'logic': 'Validated first-layer A supplies a trend-aligned MACD histogram pullback after a recent CMO extreme recovery; B adds a two-legged pullback to the short average followed by a prior-bar break. Five closed bars require recently defended pullback structure rather than accepting every ongoing parent signal; this is the second and final mixing layer.', 'parents': ['20.724', '20.293'], 'mix': 'CONFIRM', 'confirm_bars': 5, 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 24, 'be_r': 1.0}


def _load_parent(n):
    path = Path(__file__).resolve().parent.parent / f"s20.{n}" / f"strategy20_{n}.py"
    spec = importlib.util.spec_from_file_location(f"mix_parent_{n}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_A = _load_parent(724)
_B = _load_parent(293)


def _signals(module, df, tf):
    values = module.generate(df.copy(), tf)
    if isinstance(values, dict):
        values = values["sig"]
    values = np.asarray(values, dtype=np.int8)
    if len(values) != len(df):
        raise ValueError("Parent signal length mismatch")
    return values


def generate(df, tf):
    a = _signals(_A, df, tf)
    b = _signals(_B, df, tf)
    if META["mix"] == "FILTER":
        state = pd.Series(b).where(b != 0).ffill().fillna(0).to_numpy(dtype=np.int8)
        return np.where((a != 0) & (a == state), a, 0).astype(np.int8)
    # Current closed bar and four earlier closed bars: no future observations.
    buy = pd.Series(b == 1).rolling(META["confirm_bars"], min_periods=1).max().to_numpy(dtype=bool)
    sell = pd.Series(b == -1).rolling(META["confirm_bars"], min_periods=1).max().to_numpy(dtype=bool)
    out = np.zeros(len(df), dtype=np.int8)
    out[(a == 1) & buy] = 1
    out[(a == -1) & sell] = -1
    return out
