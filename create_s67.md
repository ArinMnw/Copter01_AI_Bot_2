# Create S67 - All-in-4S Clear Candle Reversal

Status: research/backtest-only, not wired to live scanner.

## Source

Derived from image-only All-in-4S PDFs:

- `เทคนิคการเทรดพี่นาย/ความลับของเเท่งเคลียร์ชนิดของเเท่งเคลียร์.pdf`
- `เทคนิคการเทรดพี่นาย/การอ่านเเรงเเท่งเทียน.pdf`
- `เทคนิคการเทรดพี่นาย/เชิงแท่งเทียน_20250803_152020_0000.pdf`

Key read:

- A clear candle forms when price is pushed hard one way and pulled back to close the opposite color.
- Type 1 has an obvious long rejection wick.
- Type 2 has a strong push and reversal pullback where the returning wick dominates.
- It should close-cover the prior candle context, not merely change candle color.

## Implementation

Files:

- `strategy67.py`
- `sim_s67_backtest.py`
- `s67_backtest_summary.csv`

Logic:

1. Detect current candle with large range.
2. Require rejection wick dominance.
3. Require close-cover of prior body or prior wick.
4. Use trend context:
   - `reversal`: clear candle appears against the prior trend.
   - `continuation`: clear candle appears with the prior trend.
5. Use the clear-candle wick extreme as SL reference.

## First Results

| Label | Days | TF | Mode | Cover | Compound PF | Compound DD | Fixed $/day | Fixed PF | Streak |
|---|---:|---|---|---|---:|---:|---:|---:|---:|
| reversal body | 90 | M5 | reversal | body | 1.05 | 9.9% | -0.21 | 0.97 | 5 |
| reversal wick | 90 | M5 | reversal | wick | 1.36 | 5.0% | -0.09 | 0.96 | 4 |
| continuation body | 90 | M5 | continuation | body | 1.13 | 5.7% | 0.56 | 1.12 | 5 |
| continuation body | 120 | M5 | continuation | body | 0.81 | 13.2% | -0.91 | 0.85 | 7 |
| continuation strict | 120 | M5 | continuation | body | 0.86 | 6.6% | -0.44 | 0.83 | 5 |
| M15 continuation | 120 | M15 | continuation | body | 0.81 | 13.6% | -1.96 | 0.51 | 6 |
| M15 reversal wick | 120 | M15 | reversal | wick | 0.30 | 12.7% | -0.86 | 0.53 | 4 |

## Verdict

S67 is not a champion and should not be used as standalone entry.

Reasons:

- 90d looked marginal, but 120d failed immediately.
- M15 transfer is poor.
- Clear candle alone is too common and needs structure context.

## Usefulness

Clear candle is still useful as a filter:

- Confirm S63/S66 only when the entry candle closes-cover prior body/wick.
- Avoid reversal entries when the clear candle appears without H/L or FVG context.
- Consider S68 with stricter 2L/2H + clear candle confirmation.

Current champion remains S63.
