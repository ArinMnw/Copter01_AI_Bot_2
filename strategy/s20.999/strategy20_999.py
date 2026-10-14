# -*- coding: utf-8 -*-
"""Causal parent confirmation; execution is provided by the shared engine."""
import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd

META = {'sid': '20.999', 'name': 'Triple MA Breakout x Marubozu Drive', 'concept': 'CONFIRM of two existing causal parent generators', 'logic': 'A supplies established trend and the band breakout; B confirms recent directional commitment through a wide-range candle with limited opposing wick. Five closed bars keep that forceful candle close to the expansion and exclude old impulses.', 'parents': ['20.422', '20.180'], 'mix': 'CONFIRM', 'confirm_bars': 5, 'sl_atr': 1.5, 'rr': 1.5, 'max_hold': 24, 'be_r': 1.0}


def _load_parent(n):
    path = Path(__file__).resolve().parent.parent / f"s20.{n}" / f"strategy20_{n}.py"
    spec = importlib.util.spec_from_file_location(f"mix_parent_{n}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_A = _load_parent(422)
_B = _load_parent(180)


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
    # Current closed bar and four earlier closed bars: no future observations.
    buy = pd.Series(b == 1).rolling(META["confirm_bars"], min_periods=1).max().to_numpy(dtype=bool)
    sell = pd.Series(b == -1).rolling(META["confirm_bars"], min_periods=1).max().to_numpy(dtype=bool)
    out = np.zeros(len(df), dtype=np.int8)
    out[(a == 1) & buy] = 1
    out[(a == -1) & sell] = -1
    return out
