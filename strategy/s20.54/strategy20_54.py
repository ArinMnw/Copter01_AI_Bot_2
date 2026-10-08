# -*- coding: utf-8 -*-
"""strategy20_54.py
Strategy S20.54: Institutional AMD Order Block Confluence

Core Innovations:
1. Multi-Strategy Single-Candle Cross-Breed Confluence (Working together on the EXACT SAME BAR):
   - SMC Macro Liquidity Sweep (Strategy 8)
   - Multi-Bar Fair Value Gap Memory (Strategy 1 & 2)
   - Strategy 11: Fibonacci Golden Zone & Premium/Discount Equilibrium Confluence
   - Strategy 15: Volume Profile Value Area (VAH/VAL)
   - Wyckoff VSA Effort vs Result: Volume Climax Ratio >= 1.20x of 20-period MA
   - Price Action Rejection Wick: lower_wick_pct / upper_wick_pct >= 30.0%
   - Candle Range Theory (CRT - Strategy 10): Closed Momentum >= 50% of total range
   - RSI Momentum Guard: BUY <= 65, SELL >= 35
2. Omni-Horizon Timeframe Matrix: M1, M5, M15, M30, H1, H4, D1
3. Precision Retest Limit Entry: 10.0% into rejection wick with 0.22 ATR SL buffer
4. Multi-Stage Quantum Ratchet Lock Engine (TP 7.50R)
5. Strict 0.01 Lot single position throughout 365 days (no scaling, no martingale, no splitting)
6. 100% Verifiable with Pessimistic SL-First execution.
"""

import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from goal_s20_53_to_100 import compute_indicators, extract_setups, run_simulation
