# Create S66 - All-in-4S FVG Ladder Follow Trend

Status: research/backtest-only, not wired to live scanner.

## Source

Derived from image-only All-in-4S PDFs:

- `เทคนิคการเทรดพี่นาย/เทคนิคการ Follw Trend.pdf`
- `4s vip/FVG.pdf`
- `เทคนิคการเทรดพี่นาย/การดูแพทเทิร์นไปต่อหรือการรับแรง.pdf`

Key read:

- A trend often creates multiple FVG levels.
- The newest FVG can fail to create a new H/L and warn of deeper pullback.
- The first/base FVG of a trend leg is often more special and stronger than later FVGs.

## Implementation

Files:

- `strategy66.py`
- `sim_s66_backtest.py`
- `s66_backtest_summary.csv`

Logic:

1. Detect a same-direction FVG ladder inside a lookback window.
2. Require at least N FVGs.
3. Select one FVG zone: `base`, `middle`, or `latest`.
4. Enter only when price retests that zone and closes back beyond the zone in trend direction.
5. Use zone + ATR buffer for SL and fixed RR for TP.

## First Results

| Label | Days | TF | Zone | Compound PF | Compound DD | Fixed $/day | Fixed PF | Streak |
|---|---:|---|---|---:|---:|---:|---:|---:|
| baseline | 90 | M5 | base | 1.07 | 20.9% | 5.32 | 1.18 | 4 |
| middle | 90 | M5 | middle | 0.95 | 40.8% | 0.18 | 1.00 | 5 |
| latest | 90 | M5 | latest | 0.84 | 82.6% | -6.50 | 0.94 | 10 |
| base rr1.6 | 90 | M5 | base | 1.09 | 23.2% | 7.39 | 1.23 | 4 |
| base rr1.6 | 120 | M5 | base | 0.89 | 42.6% | 7.30 | 1.21 | 4 |
| base rr1.6 | 150 | M5 | base | 0.93 | 40.4% | 7.11 | 1.22 | 4 |
| base rr1.6 | 180 | M5 | base | 1.00 | 35.4% | 7.56 | 1.24 | 4 |
| M15 base | 120 | M15 | base | 1.05 | 26.6% | -1.96 | 0.90 | 9 |
| M15 strict | 120 | M15 | base | 0.96 | 28.7% | -1.42 | 0.91 | 7 |
| M5 count4 rr2 | 120 | M5 | base | 1.03 | 42.4% | 7.54 | 1.21 | 5 |
| latest-fail filter | 120 | M5 | base | 0.92 | 17.3% | 0.82 | 1.06 | 8 |

## Verdict

S66 is not a standalone champion.

What worked:

- The PDF idea is confirmed: base FVG is much better than middle/latest.
- Latest FVG is actively bad as an entry zone.
- Fixed-lot PF around 1.21-1.24 is stable on M5 base FVG.

What failed:

- Compound performance is weak or negative over 120-180 days.
- The edge is too thin relative to trade frequency.
- M15 does not transfer well.

## Usefulness

S66 should be considered as a filter for S63/S64:

- Prefer S63 entries when price is reacting from base FVG ladder zone.
- Avoid S63 entries that rely on latest FVG after it fails to create a new H/L.

Current champion remains S63.
