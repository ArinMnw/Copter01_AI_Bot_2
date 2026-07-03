# Create S71 - All-in-4S Weighted Champion

Status: research/backtest-only, not wired to live scanner.

## Source

S71 continues from S70.

S70 found that:

- `S63 Normal` is the best All-in-4S entry engine.
- `S69 HC` is a high-confidence S63 subset using base FVG context.
- Running `S63 + S69` improves PF/sharpe and $/day vs S63 alone.

S71 asks:

> If S69 is a cleaner high-confidence subset, how much extra exposure should it get?

## Implementation

Files:

- `optimize_s71_allin4s_weights.py`
- `s71_allin4s_weight_search.csv`

The optimizer replays these base legs:

- `S63`: normal SP breakout engine
- `S69`: high-confidence base-FVG overlay
- `S64`: optional KRH fibo yield leg

Then it searches fixed-lot-equivalent weights:

- `S63 = 1.0` fixed base
- `S69 = 0.0 .. 4.0`
- `S64 = 0.0 .. 1.0`

Scoring priority:

1. max losing-day streak <= 3
2. highest minimum PF across 90/120/150/180d
3. average sharpe-like
4. average $/day

## Results

Fixed-lot 0.01 equivalent, spread adjusted.

### New Champion - S71

`S71 = S63 x1 + S69 x4`

| Days | PF | $/day | $/month | Streak |
|---:|---:|---:|---:|---:|
| 90 | 2.50 | 6.58 | 197.40 | 3 |
| 120 | 2.24 | 5.23 | 156.90 | 3 |
| 150 | 2.21 | 4.44 | 133.20 | 3 |
| 180 | 2.12 | 4.83 | 144.90 | 3 |

Aggregate:

- min PF: 2.119
- avg $/day: 5.27
- avg $/month: 158.07
- avg sharpe-like: 0.364
- max losing-day streak: 3

### Previous S70

`S70 = S63 x1 + S69 x1`

| Days | PF | $/day | $/month | Streak |
|---:|---:|---:|---:|---:|
| 90 | 2.25 | 4.01 | 120.43 | 3 |
| 120 | 1.90 | 2.99 | 89.65 | 3 |
| 150 | 1.89 | 2.64 | 79.30 | 3 |
| 180 | 1.80 | 2.63 | 78.92 | 3 |

### Yield Variant

`S71-Y = S63 x1 + S69 x4 + S64 x0.25`

| Days | PF | $/day | $/month | Streak |
|---:|---:|---:|---:|---:|
| 90 | 2.24 | 7.07 | 212.10 | 3 |
| 120 | 2.09 | 5.87 | 176.10 | 3 |
| 150 | 2.02 | 4.84 | 145.20 | 3 |
| 180 | 2.00 | 5.29 | 158.70 | 3 |

This yields more money but lower min PF and lower sharpe-like than pure S71.

## Verdict

S71 is the new All-in-4S champion candidate.

Why it beats S70:

- Raises min PF from about 1.80 to 2.12.
- Raises average $/month from about $92 to about $158 per 0.01-lot equivalent.
- Keeps max losing-day streak at 3.
- Does not rely on S64, which added yield but lowered quality.

## Interpretation

S71 is not a new chart pattern. It is a position-sizing discovery:

- S63 gives normal signal flow.
- S69 identifies the same family of signal when base-FVG context is present.
- S69 deserves higher exposure because it is materially cleaner.

In live terms, this is equivalent to:

- normal S63 signal: 0.01 lot
- S69 high-confidence signal: additional 0.04 lot

If both fire on the same setup family, total exposure can become 0.05 lot. This must be checked against account risk before live wiring.

## Recommendation

Promote:

- `S71 All-in-4S Weighted Champion = S63 x1 + S69 x4`

Keep optional:

- `S71-Y = S63 x1 + S69 x4 + S64 x0.25`

Next work before live/demo wiring:

1. Add max simultaneous exposure guard.
2. Decide whether S69 x4 should be one 0.04-lot order or four logical 0.01-lot legs.
3. Ensure order comments identify `S71-S63` and `S71-S69`.
4. Add Telegram toggle separate from existing P13/P16.
5. Re-run signal consistency after wiring.
