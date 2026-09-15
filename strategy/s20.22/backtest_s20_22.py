# -*- coding: utf-8 -*-
"""backtest_s20_22.py
Direct backtest runner for Strategy S20.22 (Session Anchored VWAP Reversion).
Supports all symbols, symbol lot weights, LTS_AUS3 CLI arguments, and CSV outputs.
"""
import sys
import os

strategy_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if strategy_dir not in sys.path:
    sys.path.insert(0, strategy_dir)

from backtest_s20_unified import main

if __name__ == "__main__":
    main(default_strategy="S20_22")
