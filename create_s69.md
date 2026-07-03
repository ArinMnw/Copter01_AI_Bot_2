# Create S69 - All-in-4S S63 Filter Stack

Status: research/backtest-only, not wired to live scanner.

## Source

Built from previous research:

- S63 DMxSP/SP breakout is the strongest All-in-4S entry engine so far.
- S66 showed base FVG is much better than middle/latest FVG.
- S67 showed clear candle is not reliable as standalone and can be too restrictive.
- S68 showed 2L/2H fail-to-break is not reliable as standalone.

## Implementation

Files:

- `strategy69.py`
- `sim_s69_backtest.py`
- `s69_backtest_summary.csv`

Logic:

1. Run S63 robust-A engine:
   - M5
   - SP breakout
   - `SP_LOOKBACK=8`
   - `SP_MAX_ATR=1.4`
   - `FVG_REQUIRED=False`
   - `MIN_BODY_ATR=0.35`
   - `MIN_BODY_RATIO=0.40`
   - `SL_ATR_MULT=0.35`
   - `TP_RR=1.20`
2. Optional filters:
   - base FVG touch context from S66
   - clear candle confirmation from S67

## Results

| Label | Days | Filters | Trades | Compound PF | Compound DD | Fixed $/day | Fixed PF | Streak |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| S63 recheck | 90 | none | 42 | 1.85 | 5.6% | 3.16 | 2.12 | 3 |
| S69 base | 90 | base FVG | 9 | 3.18 | 2.6% | 0.86 | 3.18 | 1 |
| S69 base+clear | 90 | base FVG + clear | 0 | 0.00 | 0.0% | 0.00 | 0.00 | 0 |
| S69 base | 120 | base FVG | 10 | 3.53 | 2.6% | 0.75 | 3.53 | 1 |
| S69 base | 150 | base FVG | 10 | 3.53 | 2.6% | 0.60 | 3.53 | 1 |
| S69 base | 180 | base FVG | 14 | 3.11 | 2.7% | 0.73 | 3.11 | 1 |
| S69 base touch 0.5 | 180 | base FVG loose | 17 | 2.65 | 2.7% | 0.70 | 2.65 | 1 |

## Verdict

S69 is not a standalone champion because trade count and $/day are too low.

However, S69 is the best high-confidence overlay found so far:

- PF above 3.0 over 90-180 days.
- max losing-day streak 1.
- drawdown around 2.6-2.7%.
- It confirms that base FVG context is useful when attached to S63.

## Recommendation

Keep two S63 modes:

- `S63 Normal`: current champion candidate, more trades and higher $/day.
- `S69/S63-HC`: high-confidence filter mode, fewer trades but much cleaner PF/DD.

Do not use S67 clear filter as required confirmation; it removes too many valid S63 trades.

Current champion remains S63 Normal, with S69 as a high-confidence variant.
