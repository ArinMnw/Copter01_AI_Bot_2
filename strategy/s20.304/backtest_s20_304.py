# -*- coding: utf-8 -*-
"""backtest_s20_304.py
Direct runner alias for Strategy S20.304 verified multi-asset backtest.
Identical CLI arguments and CSV outputs as LTS_AUS3 (run_backtest_sim.py).
"""
import sys
import os

# Delegate directly to run_s20_304_m5_verified.py
from run_s20_304_m5_verified import main

if __name__ == "__main__":
    main()
