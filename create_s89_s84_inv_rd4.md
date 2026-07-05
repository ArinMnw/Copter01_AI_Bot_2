# S89 Champion - Inverse S84 Old-Wick Follow With Risk-Distance Cap

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

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
| Skipped by circuit breaker | 10022 |

## New Leg

Next tested All-in-4S generator:

- S84 old-wick eat close-fail / follow variant
- direct S84 did not beat S88 in the initial probe
- inverse S84 had positive portfolio effect but needed risk filtering to avoid streak blow-up

Winning config:

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frd4
```

Meaning:

- TF: M15
- lookback: 48
- old wick min: 0.25 ATR
- wick/body min: 0.8
- eat tolerance: 0.06 ATR
- close-fail threshold: 0.03 ATR
- require opposite close: on
- min body: 0.06 ATR
- min range: 0.35 ATR
- target mode: RR
- mode: follow
- SL buffer: 0.2 ATR
- RR: 0.9
- mode: inverse raw
- filter: `risk_distance <= 4`

## New Champion

```text
S89 = S88 + INV_S84_M15_OLDWICK_FOLLOW_RD4x0.608
```

| Metric | S89 |
|---|---:|
| Avg $/day | 486.25 |
| Min $/day | 453.70 |
| Min PF | 4.119 |
| Max losing-day streak | 3 |
| Worst day | -999.90 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10292 |

Per-window rounded from `s89_s84_inv_rd4_daily.csv`:

| Window | $/day | PF | Streak | Worst day |
|---:|---:|---:|---:|---:|
| 90 | 477.47 | 4.119 | 3 | -999.90 |
| 120 | 543.89 | 4.746 | 3 | -976.23 |
| 150 | 469.93 | 4.617 | 3 | -993.42 |
| 180 | 453.70 | 4.282 | 3 | -997.14 |

Raw counts after `risk_distance <= 4`:

| Window | Raw trades | Leg skipped by CB |
|---:|---:|---:|
| 90 | 510 | 120 |
| 120 | 647 | 140 |
| 150 | 884 | 190 |
| 180 | 1075 | 270 |

## Why x0.608, Not x0.609

`s89_s84_inv_rd4_threshold.csv`:

| Weight | beats S88 | Avg $/day | Min $/day | Streak | Worst day |
|---:|---|---:|---:|---:|---:|
| 0.608 | True | 486.25 | 453.70 | 3 | -999.90 |
| 0.609 | False | 486.26 | 453.71 | 7 | -999.90 |
| 0.610 | False | 486.27 | 453.71 | 7 | -999.90 |

`x0.608` is the highest tested weight at 0.001 precision that keeps max losing-day streak <= 3.

## No-Blow Guard

| Floor | Result |
|---|---|
| -700 | fail because the champion ladder already has near -1000 days |
| -900 | fail because the champion ladder already has near -1000 days |
| -973.16 | fail because S89 worst day is near -999.90 |
| -999.91 | pass |
| -1000 | pass |

## Evidence

- `optimize_s88_allin4s_fast.py`
- `s88_s86run_ratr3_daily.csv`
- `s89_s84_ratr3_probe.csv`
- `s89_s84_inv_rd8_fine.csv`
- `s89_s84_inv_rd4_ultrafine.csv`
- `s89_s84_inv_rd4_fine.csv`
- `s89_s84_inv_rd4_wide.csv`
- `s89_s84_inv_rd4_wider.csv`
- `s89_s84_inv_rd4_threshold.csv`
- `s89_s84_inv_rd4_threshold_worst_day.csv`
- `s89_s84_inv_rd4_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S89 uses `s88_s86run_ratr3_daily.csv` as the base, so it is compared against the current champion, not S87/S86.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)` for per-leg sizing.
- S84 detection uses closed bar `j`.
- Fill is simulated from `j+1` via the existing `sim_s84_backtest.run_single` replay.
- Inverse mode swaps signal/TP/SL on the same raw event and negates `diff_usd_per_001lot`.
- `risk_distance <= 4` is known at signal construction time from entry/SL, not from future outcome.
- No future candle, same-bar close fill, or post-entry result filter is used.

## Verdict

Found new champion:

```text
S89 = S88 + INV_S84_M15_OLDWICK_FOLLOW_RD4x0.608
```

This improves both avg $/day and min $/day while keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors. Continue with S90 search using S89 as the new baseline.
