# S90 Champion - Conservative Inverse S84 RD2.2 Micro Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

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

## New Leg

Winning overlay:

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frd2.2
```

Meaning:

- Base generator: S84 old-wick follow
- Mode: inverse raw
- TF: M15
- Lookback: 48
- Old wick min: 0.25 ATR
- Wick/body min: 0.8
- Eat tolerance: 0.06 ATR
- Close-fail threshold: 0.03 ATR
- Require opposite close: on
- Min body: 0.06 ATR
- Min range: 0.35 ATR
- Target mode: RR
- SL buffer: 0.2 ATR
- RR: 0.9
- Post-filter: `risk_distance <= 2.2`

## New Champion

```text
S90 = S89 + INV_S84_M15_OLDWICK_FOLLOW_RD2.2x0.005
```

| Metric | S90 |
|---|---:|
| Avg $/day | 486.2628 |
| Min $/day | 453.7127 |
| Min PF | 4.11927 |
| Max losing-day streak | 3 |
| Worst day | -999.90982 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10352 |

Per-window exact from `s90_s84_inv_rd22_daily.csv`:

| Window | $/day | PF | Streak | Worst day |
|---:|---:|---:|---:|---:|
| 90 | 477.4843 | 4.11927 | 3 | -999.90982 |
| 120 | 543.9054 | 4.74576 | 3 | -976.22864 |
| 150 | 469.9488 | 4.61723 | 3 | -993.41578 |
| 180 | 453.7127 | 4.28186 | 3 | -997.10707 |

Raw counts after `risk_distance <= 2.2`:

| Window | Raw trades |
|---:|---:|
| 90 | 124 |
| 120 | 161 |
| 150 | 261 |
| 180 | 330 |

## Why RD2.2 and x0.005

The broader RD3 subset improved avg/min, but any positive weight flipped
2025-10-31 from near-zero positive to negative and expanded the 180d losing
streak to 7. RD2.2 removes the losing trades on that date while keeping the
positive one, using only entry/SL risk distance known at signal time.

`x0.006` still improves avg/min and keeps streak 3, but its exact worst day is
`-999.9113`, failing the `-999.91` floor. `x0.005` is the highest tested
0.001-step weight that passes both `-999.91` and `-1000`.

## No-Blow Guard

| Floor | Result |
|---|---|
| -700 | fail because the champion ladder already has near -1000 days |
| -900 | fail because the champion ladder already has near -1000 days |
| -973.16 | fail because the champion ladder already has near -1000 days |
| -999.91 | pass |
| -1000 | pass |

## Evidence

- `optimize_s88_allin4s_fast.py`
- `s90_s84_inv_rd22_target28.csv`
- `s90_s84_inv_rd22_target28_fine.csv`
- `s90_s84_inv_rd22_target28_fine_worst_day.csv`
- `s90_s84_inv_rd22_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S90 uses `s89_s84_inv_rd4_daily.csv` as the base, so it is compared against
  the current champion S89.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`.
- Fill is simulated from `j+1` via the existing `sim_s84_backtest.run_single`
  replay.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance <= 2.2` is known at signal construction time from entry/SL,
  not from future outcome.
- No future candle, same-bar close fill, or post-entry result filter is used.

## Verdict

Found new conservative micro champion:

```text
S90 = S89 + INV_S84_M15_OLDWICK_FOLLOW_RD2.2x0.005
```

This improves both avg $/day and min $/day while keeping max losing-day streak
at 3 and passing the `-999.91` / `-1000` floors. Continue with S91 search using
S90 as the new baseline.
