# -*- coding: utf-8 -*-
"""strategy20_301.py
Strategy S20.301: Multi-Timeframe Institutional Synergy & Sniper Extension

Core Innovations:
1. แนวทางที่ 1: การผสานโครงสร้างแนวโน้มข้ามไทม์เฟรม (HTF Extension) ควบคู่กับจุดเข้า Sniper ละเอียดระดับสถาบัน
2. Multi-Strategy Single-Candle Cross-Breed Confluence:
   - SMC Macro Liquidity Sweep: Asian + London + NY + PDH/PDL + PWH/PWL + PMH/PML + PQH/PQL + PYH/PYL + Swings + HTF 24 Swings
   - Inversion FVG (IFVG): Polarity Reversal Institutional Zone
   - Breaker Block (BB) & Optimal Trade Entry (OTE 70.5%/78.6%) Alignment
   - London-NY Overlap Acceleration (12:00 - 16:00 UTC)
   - Wyckoff Spring & UTAD Accumulation/Distribution Confirmation
   - Multi-Bar Fair Value Gap Memory (Strategy 1 & 2): 6-bar historical imbalance
   - Strategy 11: Fibonacci Golden Zone 38.2% / 61.8% Equilibrium
   - Strategy 15: Volume Profile Value Area (VAH/VAL) Absorption
   - Wyckoff VSA Effort vs Result: Volume Climax Ratio >= 1.11x
   - Candle Range Theory (CRT - Strategy 10): Closed Momentum >= 45% of total range
3. Omni-Horizon Timeframe Matrix: H4, H3, H2, H1, M30, M20, M15, M12
4. Multi-Stage Quantum Ratchet Lock Engine (55 Stages, TP 13.43R)
5. Parameter Delta: Depth Offset +0.0010, SL Mult Offset +0.0000
"""

CONFIG = {
    "version": "S20.301",
    "name": "Multi-Timeframe Institutional Synergy & Sniper Extension",
    "target_asset": "XAUUSD.iux",
    "execution_timeframe": "M5",
    "lot_size": 0.01,
    "tp_r": 13.43,
    "stages_count": 55,
    "depth_delta": 0.001,
    "sl_delta": 0.0,
    "stages": [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3), (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1), (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85), (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45), (8.8, 8.6), (8.95, 8.75), (9.1, 8.9), (9.25, 9.05), (9.4, 9.2), (9.55, 9.35), (9.7, 9.5), (9.85, 9.65), (10.0, 9.8), (10.15, 9.95), (10.3, 10.1), (10.45, 10.25), (10.6, 10.4), (10.75, 10.55), (10.9, 10.7), (11.05, 10.85), (11.2, 11.0), (11.35, 11.15), (11.5, 11.3), (11.65, 11.45), (11.8, 11.6), (11.95, 11.75), (12.1, 11.9), (12.25, 12.05), (12.4, 12.2), (12.55, 12.35)]
}
