# Create S70 - All-in-4S Mini Portfolio

Status: research/backtest-only, not wired to live scanner.

## Source

S70 is the first All-in-4S portfolio-style candidate from this research branch.

It combines:

- `S63 Normal`: best current standalone All-in-4S entry engine.
- `S69 HC`: high-confidence S63 overlay using base FVG context.
- optional `S64`: KRH fibo expansion secondary leg.

This follows the same principle as the existing repo champion document: the best system is likely a portfolio of decorrelated legs, not a single pattern.

## Implementation

Files:

- `sim_s70_allin4s_portfolio.py`
- `s70_allin4s_portfolio_summary.csv`

S70 does not define new live scanner logic yet. It is a research portfolio simulator that combines raw trades from existing research-only legs.

## Results

Fixed-lot 0.01, spread adjusted.

### S63 Normal

| Days | Trades | $/day | $/month | PF | Sharpe-like | Streak |
|---:|---:|---:|---:|---:|---:|---:|
| 90 | 42 | 3.16 | 94.73 | 2.12 | 0.338 | 3 |
| 120 | 52 | 2.24 | 67.24 | 1.74 | 0.245 | 3 |
| 150 | 66 | 2.05 | 61.38 | 1.75 | 0.238 | 3 |
| 180 | 81 | 1.90 | 56.94 | 1.65 | 0.232 | 3 |

### S70 Candidate - S63 + S69

| Days | Trades | $/day | $/month | PF | Sharpe-like | Streak |
|---:|---:|---:|---:|---:|---:|---:|
| 90 | 51 | 4.01 | 120.43 | 2.25 | 0.401 | 3 |
| 120 | 62 | 2.99 | 89.65 | 1.90 | 0.307 | 3 |
| 150 | 76 | 2.64 | 79.30 | 1.89 | 0.289 | 3 |
| 180 | 95 | 2.63 | 78.92 | 1.80 | 0.280 | 3 |

### Yield Variant - S63 + S64 + S69

| Days | Trades | $/day | $/month | PF | Sharpe-like | Streak |
|---:|---:|---:|---:|---:|---:|---:|
| 120 | 111 | 5.57 | 167.14 | 1.69 | 0.261 | 3 |
| 180 | 164 | 4.49 | 134.67 | 1.62 | 0.234 | 4 |

## Verdict

S70 `S63 + S69` is the new best All-in-4S candidate from this branch.

Why:

- Beats S63 Normal on every tested window for PF, $/day, and sharpe-like.
- Keeps max losing-day streak at 3 days.
- Adds S69's high-confidence base FVG edge without reducing trade count too aggressively.
- More robust than S64-inclusive version, which raises raw $ but reduces PF/sharpe and worsens 180d streak.

## Recommendation

Promote:

- `S70 All-in-4S Mini Portfolio = S63 Normal + S69 HC`

Keep as optional high-yield variant:

- `S70-Y = S63 + S64 + S69`

Do not wire live yet. Next step should be a live-safe integration plan:

1. Decide whether S70 belongs in `demo_portfolio.py` as new All-in-4S portfolio legs.
2. Add strategy IDs/comments without touching existing S1-S20 runtime.
3. Add Telegram toggles for S70 Normal / S70-Y if needed.
4. Re-run fixed-lot validation after wiring to avoid signal drift.
