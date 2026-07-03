# Create S65 - All-in-4S Fake Reversal Trap

Status: research/backtest-only, not wired to live scanner.

## Source

Derived from image-only All-in-4S PDFs:

- `เทคนิคการเทรดพี่นาย/โครงสร้างหลอกกลับตัว_20250803_152119_0000.pdf`
- `โครงสร้างกลับตัวหลอก.pdf`
- `เทคนิคการเทรดพี่นาย/โครงสร้าง 2L 2H.pdf`
- `เทคนิคการเทรดพี่นาย/ความลับของเเท่งเคลียร์ชนิดของเเท่งเคลียร์.pdf`

Key read:

- Fake reversal can happen in the middle of an H-L / L-H structure.
- Several candles may fail to close-cover their wick, then one candle closes-cover and forces a fake counter move.
- The trade should not enter on the fake reversal itself. It should wait until the fake move fails and price closes back in the original impulse direction.

## Implementation

Files:

- `strategy65.py`
- `sim_s65_backtest.py`
- `optimize_s65.py`
- `s65_backtest_summary.csv`

Logic:

1. Detect a recent impulse leg.
2. Detect a counter retrace within a controlled retracement window.
3. Require a fake extreme with wick/force context.
4. Enter only after close-cover failure back toward the original impulse.
5. Use the fake extreme as SL reference.
6. TP via fixed RR or origin target.

## First Results

Baseline 90d M5:

- signals: 1116
- compound: +$7.64/day, PF 1.18, DD 26.0%
- fixed 0.01 lot: +$6.64/day, PF 1.07, max losing-day streak 7

Manual candidates:

| Label | Days | TF | Compound PF | Compound DD | Fixed $/day | Fixed PF | Streak |
|---|---:|---|---:|---:|---:|---:|---:|
| baseline | 90 | M5 | 1.18 | 26.0% | 6.64 | 1.07 | 7 |
| loose rr0.9 | 90 | M5 | 0.96 | 44.0% | -0.63 | 0.99 | 6 |
| strict rr1.15 | 90 | M5 | 1.06 | 28.3% | 5.43 | 1.07 | 5 |
| loose rr0.9 | 90 | M15 | 1.10 | 34.9% | 3.45 | 1.07 | 6 |
| strict rr1.15 | 90 | M15 | 1.33 | 24.6% | 3.49 | 1.07 | 6 |
| strict rr1.15 | 120 | M15 | 1.44 | 19.8% | 5.15 | 1.10 | 6 |
| strict rr1.15 | 150 | M15 | 1.09 | 64.9% | 2.95 | 1.06 | 7 |
| strict rr1.15 | 180 | M15 | 1.09 | 62.0% | 4.19 | 1.10 | 7 |

## Verdict

S65 version 1 is not a champion.

Reasons:

- Fixed-lot PF stays near 1.06-1.10.
- Losing-day streak remains 6-7 days.
- Longer windows expose severe compound drawdown.
- The signal fires too often and still catches many ordinary pullbacks, not only true fake reversals.

## Next Split

Do not tune S65 deeper as-is. Split it:

- S66: FVG Ladder Follow Trend filter from `เทคนิคการ Follw Trend.pdf`
- S67: Clear Candle / wick-clear model from `ความลับของเเท่งเคลียร์ชนิดของเเท่งเคลียร์.pdf`
- S68: 2L/2H fail-to-break only, with stricter H/L confirmation and fewer trades

Current champion remains S63.
