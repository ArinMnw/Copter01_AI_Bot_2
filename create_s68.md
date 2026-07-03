# Create S68 - All-in-4S 2L/2H Fail-to-Break

Status: research/backtest-only, not wired to live scanner.

## Source

Derived from All-in-4S notes:

- `เทคนิคการเทรดพี่นาย/โครงสร้าง 2L 2H.pdf`
- `เทคนิคการเทรดพี่นาย/โครงสร้างหลอกกลับตัว_20250803_152119_0000.pdf`
- `เทคนิคการเทรดพี่นาย/เทคนิคการ Follw Trend.pdf`
- `เทคนิคการเทรดพี่นาย/ความลับของเเท่งเคลียร์ชนิดของเเท่งเคลียร์.pdf`

Key read:

- After 2L, if price cannot break the prior H, it can become a sell reversal.
- After 2H, if price cannot break the prior L, it can become a buy reversal.
- 2L/2H should not be used alone. It needs fail-to-break confirmation and structure context.

## Implementation

Files:

- `strategy68.py`
- `sim_s68_backtest.py`
- `s68_backtest_summary.csv`

Logic:

1. Detect local pivot lows/highs.
2. Identify 2L or 2H inside a recent structure.
3. For 2L, require failure to break prior H and bearish break trigger.
4. For 2H, require failure to break prior L and bullish break trigger.
5. Optional filters:
   - clear candle confirmation
   - base FVG touch context
6. Use failed-structure extreme as SL and fixed RR TP.

## First Results

| Label | Days | TF | Filters | Trades | Compound PF | Compound DD | Fixed $/day | Fixed PF | Streak |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| baseline | 90 | M5 | clear + base FVG | 1 | 0.00 | 2.2% | -0.24 | 0.00 | 1 |
| no base FVG | 90 | M5 | clear only | 22 | 0.00 | 12.4% | -1.50 | 0.57 | 5 |
| no clear | 90 | M5 | base FVG only | 31 | 1.19 | 5.0% | -0.35 | 0.92 | 3 |
| relaxed base | 90 | M5 | base FVG only | 71 | 0.57 | 26.5% | -1.62 | 0.81 | 4 |
| relaxed clear | 90 | M5 | clear + base FVG | 4 | 0.54 | 2.1% | -0.22 | 0.54 | 2 |
| M15 relaxed base | 90 | M15 | base FVG only | 16 | 0.31 | 13.3% | -2.24 | 0.42 | 9 |
| relaxed rr1.8 | 90 | M5 | base FVG only | 71 | 0.65 | 23.1% | -2.71 | 0.73 | 7 |

## Verdict

S68 is not a champion.

Reasons:

- Strict version barely fires.
- Relaxed version catches noise and loses.
- Base FVG helps compared with no-base, but not enough to create standalone edge.
- Clear candle confirmation is too restrictive in this structure form.

## Next Step

Do not tune S68 further as standalone.

Better direction:

- S69 should combine the actual champion candidate S63 with S66/S67 filters:
  - S63 DMxSP breakout as entry engine
  - S66 base FVG context as quality filter
  - S67 clear candle as optional trigger confirmation

Current champion remains S63.
