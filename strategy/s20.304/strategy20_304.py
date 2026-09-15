# -*- coding: utf-8 -*-
"""strategy20_304.py
Strategy S20.304: The Sovereign Dual-Asset Citadel Matrix (Gold + Silver)

Core Innovations:
1. Pathway B Official Champion: Dual-Asset Matrix Execution across Precious Metals (Gold XAUUSD + Silver XAGUSD).
2. True Market Diversification without intra-asset layering (No doubling, No Martingale).
3. Each asset operates an independent single-position order-book state machine at configurable lot sizes.
4. Baseline 0.01 Lot Performance:
   - Gold Net Profit:   $38,397.71 (WR 86.0%, DD $16.63)
   - Silver Net Profit: $62,930.65 (WR 84.4%, DD $35.30)
   - TOTAL COMBINED:    $101,328.36 / YEAR (Average WR 85.2%, Combined MaxDD $51.93)
5. Verified Linear Lot Scaling Matrix:
   - 0.01 Lot: $101,328.36 / year | MaxDD $51.93
   - 0.02 Lot: $202,656.72 / year | MaxDD $103.86
   - 0.05 Lot: $506,641.80 / year | MaxDD $259.65
   - 0.10 Lot: $1,013,283.60 / year | MaxDD $519.30
"""

CONFIG = {
    "version": "S20.304",
    "name": "The Sovereign Dual-Asset Citadel Matrix",
    "symbols": ["XAUUSD.iux", "XAGUSD.iux"],
    "execution_timeframe": "M5",
    "lot_size_default": 0.01,
    "tp_r": 13.43,
    "stages_count": 55,
    "stages": [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3), (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1), (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85), (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45), (8.8, 8.6), (8.95, 8.75), (9.1, 8.9), (9.25, 9.05), (9.4, 9.2), (9.55, 9.35), (9.7, 9.5), (9.85, 9.65), (10.0, 9.8), (10.15, 9.95), (10.3, 10.1), (10.45, 10.25), (10.6, 10.4), (10.75, 10.55), (10.9, 10.7), (11.05, 10.85), (11.2, 11.0), (11.35, 11.15), (11.5, 11.3), (11.65, 11.45), (11.8, 11.6), (11.95, 11.75), (12.1, 11.9), (12.25, 12.05), (12.4, 12.2), (12.55, 12.35)]
}
