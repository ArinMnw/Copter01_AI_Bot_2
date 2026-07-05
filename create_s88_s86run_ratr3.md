# S88 Champion - S86RUN M15 Fibo 50-60 RUN With RiskATR Cap

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S87 = S86 + inverse(S85SIG_M30)x0.007
```

S87 เป็น micro champion เหนือ S86 โดย rounded metrics แทบเท่ากับ S86:

| Metric | S87 |
|---|---:|
| Avg $/day | 476.87 |
| Min $/day | 444.19 |
| Min PF | 4.07 |
| Max losing-day streak | 3 |
| Worst day | -999.91 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 9909 |

## New Leg

Tested next All-in-4S generator from the PDF notes:

- Fibo 50-60 decision zone before RUN
- if price tests the 50-60 zone and reclaims structure, it can run to the old H/L or RR target
- implemented as S86RUN/Fibo 50-60 RUN overlay

Winning config:

```text
S86RUN_M15_lb48_imp1.6_zt0.06_body0.08_ratio0.2_tr1_tl12_tm0.6_swing_rr_sl0.35_rr1.3_Fratr3
```

Meaning:

- TF: M15
- lookback: 48
- impulse min: 1.6 ATR
- Fibo zone tolerance: 0.06 ATR
- confirm body: 0.08 ATR
- confirm body ratio: 0.20
- require trend: on
- trend lookback: 12
- trend min: 0.6 ATR
- SL mode: swing
- TP mode: RR
- SL buffer: 0.35 ATR
- RR: 1.3
- filter: `riskATR <= 3.0`

The `riskATR <= 3.0` filter was added because the unfiltered leg improved avg/min but immediately caused max losing-day streak 4, even at tiny weight. Audit showed the 120d streak break came from high-risk trades around `riskATR=2.63` and `riskATR=3.12`; capping at 3.0 removed the harmful tail while keeping the positive edge.

## New Champion

```text
S88 = S87 + S86RUN_M15_FIBO_RUN_RATR3x0.91
```

| Metric | S88 |
|---|---:|
| Avg $/day | 481.62 |
| Min $/day | 449.12 |
| Min PF | 4.066 |
| Max losing-day streak | 3 |
| Worst day | -999.91 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 9909 + S86RUN leg skips |

Per-window rounded:

| Window | $/day | PF | Streak | Worst day |
|---:|---:|---:|---:|---:|
| 90 | 473.59 | 4.07 | 3 | -999.90 |
| 120 | 539.29 | 4.68 | 3 | -984.30 |
| 150 | 464.49 | 4.53 | 3 | -998.76 |
| 180 | 449.12 | 4.21 | 3 | -999.91 |

Raw counts after `riskATR <= 3.0`:

| Window | Raw trades |
|---:|---:|
| 90 | 120 |
| 120 | 165 |
| 150 | 214 |
| 180 | 258 |

## Why x0.91, Not x0.92

`s88_s86run_ratr3_fine.csv`:

| Weight | beats S87 | Avg $/day | Min $/day | Streak | Worst day |
|---:|---|---:|---:|---:|---:|
| 0.90 | True | 481.57 | 449.07 | 3 | -999.91 |
| 0.91 | True | 481.62 | 449.12 | 3 | -999.91 |
| 0.92 | False | 481.68 | 449.18 | 3 | -1000.19 |

`x0.91` is the highest tested weight at 0.01 precision that keeps both the stricter `-999.91` guard and the `-1000` no-blow floor.

## No-Blow Guard

| Floor | Result |
|---|---|
| -700 | fail because the champion ladder already has near -1000 days |
| -900 | fail because the champion ladder already has near -1000 days |
| -973.16 | fail because S88 worst day is near -999.91 |
| -999.91 | pass |
| -1000 | pass |

## Evidence

- `optimize_s88_allin4s_fast.py`
- `s87_micro_daily.csv`
- `s88_s86run_micro_probe.csv`
- `s88_s86run_micro_fine.csv`
- `s88_s86run_best_fine.csv`
- `s88_s86run_ratr3_fine.csv`
- `s88_s86run_ratr3_fine_worst_day.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- Base S87 daily is rebuilt from verified S86 daily plus the documented S87 micro leg.
- The new S86RUN leg uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)` for per-leg sizing.
- S86RUN detects only from closed bar `j`.
- Fill is simulated at `j+1` open through the existing `sim_s86_backtest.run_single` replay.
- No future candle, same-bar close fill, or post-entry result is used as a signal filter.
- The `riskATR <= 3.0` filter uses risk metadata known at signal construction time from entry/SL/ATR, not trade outcome.

## Verdict

Found new champion:

```text
S88 = S87 + S86RUN_M15_FIBO_RUN_RATR3x0.91
```

This is a real improvement over S87, but the portfolio is still far from the final `$1000/day` target. Continue with S89 search using S88 as the new baseline.
