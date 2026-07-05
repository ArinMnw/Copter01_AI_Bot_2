# S91 Champion - Scaled Inverse S84 RD2 Hedge

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

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

## New Leg

Winning overlay:

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frd2
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
- Post-filter: `risk_distance <= 2.0`

## New Champion

```text
S91 = S90 + INV_S84_M15_OLDWICK_FOLLOW_RD2x50.848
```

| Metric | S91 |
|---|---:|
| Avg $/day | 590.5990 |
| Min $/day | 566.2649 |
| Min PF | 5.08383 |
| Max losing-day streak | 3 |
| Worst day | -999.8974 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10391 |

Per-window exact from `s91_s84_inv_rd20_daily.csv`:

| Window | $/day | PF | Streak | Worst day |
|---:|---:|---:|---:|---:|
| 90 | 566.2649 | 5.08383 | 3 | -978.3384 |
| 120 | 630.5886 | 5.73086 | 3 | -976.22864 |
| 150 | 591.8145 | 5.70519 | 3 | -986.25864 |
| 180 | 573.7281 | 5.36807 | 3 | -999.8974 |

Raw counts after `risk_distance <= 2.0`:

| Window | Raw trades |
|---:|---:|
| 90 | 87 |
| 120 | 117 |
| 150 | 199 |
| 180 | 249 |

## Weight Threshold

`s91_s84_inv_rd20_target28_threshold.csv`:

| Weight | Avg $/day | Min $/day | Streak | Worst day | Floor -999.91 |
|---:|---:|---:|---:|---:|---|
| 50.848 | 590.5990 | 566.2649 | 3 | -999.8974 | PASS |
| 50.849 | 590.6011 | 566.2666 | 3 | -999.9127 | FAIL |

`x50.848` is the highest tested 0.001-step weight that keeps the `-999.91`
floor while improving both avg $/day and min $/day.

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
- `s91_s84_inv_rd20_target28_probe.csv`
- `s91_s84_inv_rd20_target28_wide.csv`
- `s91_s84_inv_rd20_target28_mega.csv`
- `s91_s84_inv_rd20_target28_ultra.csv`
- `s91_s84_inv_rd20_target28_fine.csv`
- `s91_s84_inv_rd20_target28_threshold.csv`
- `s91_s84_inv_rd20_target28_threshold_worst_day.csv`
- `s91_s84_inv_rd20_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S91 uses `s90_s84_inv_rd22_daily.csv` as the base, so it is compared against
  the current champion S90.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`.
- Fill is simulated from `j+1` via the existing `sim_s84_backtest.run_single`
  replay.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance <= 2.0` is known at signal construction time from entry/SL,
  not from future outcome.
- No future candle, same-bar close fill, or post-entry result filter is used.

## Verdict

Found new champion:

```text
S91 = S90 + INV_S84_M15_OLDWICK_FOLLOW_RD2x50.848
```

This improves both avg $/day and min $/day while keeping max losing-day streak
at 3 and passing the `-999.91` / `-1000` floors. Continue with S92 search using
S91 as the new baseline.
