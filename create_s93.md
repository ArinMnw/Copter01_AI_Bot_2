# S93 Champion - Pre-9AM Inverse S84 RD2 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S92 = S91 + INV_S84_M15_OLDWICK_FOLLOW_RD2_HBEFORE10x34.552
```

| Metric | S92 |
|---|---:|
| Avg $/day | 604.5594 |
| Min $/day | 582.7654 |
| Min PF | 5.18014 |
| Max losing-day streak | 3 |
| Worst day | -999.90954 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10391 |

## New Leg

Winning overlay:

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frd2_hbefore9
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
- Time filter: `fill_hour < 9` BKK

## New Champion

```text
S93 = S92 + INV_S84_M15_OLDWICK_FOLLOW_RD2_HBEFORE9x9.48
```

| Metric | S93 |
|---|---:|
| Avg $/day | 607.9415 |
| Min $/day | 587.3495 |
| Min PF | 5.21773 |
| Max losing-day streak | 3 |
| Worst day | -999.90591 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10391 |

Per-window exact from `s93_s84_inv_rd20_h9_daily.csv`:

| Window | $/day | PF | Streak | Worst day |
|---:|---:|---:|---:|---:|
| 90 | 587.3495 | 5.21773 | 3 | -978.3384 |
| 120 | 647.0680 | 5.76904 | 3 | -976.22864 |
| 150 | 607.6038 | 5.64101 | 3 | -999.90591 |
| 180 | 589.7445 | 5.31154 | 3 | -997.10707 |

Raw counts after `risk_distance <= 2.0` and `fill_hour < 9`:

| Window | Raw trades |
|---:|---:|
| 90 | 11 |
| 120 | 12 |
| 150 | 21 |
| 180 | 30 |

## Weight Threshold

`s93_s84_inv_rd20_h9_target28_threshold.csv`:

| Weight | Avg $/day | Min $/day | Streak | Worst day | Floor -999.91 |
|---:|---:|---:|---:|---:|---|
| 9.480 | 607.9415 | 587.3495 | 3 | -999.90591 | PASS |
| 9.481 | ~607.94 | ~587.35 | 3 | below -999.91 | FAIL |

`x9.48` is the highest tested 0.001-step weight that keeps the `-999.91`
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
- `s93_s84_inv_rd20_h9_target28_probe.csv`
- `s93_s84_inv_rd20_h9_target28_fine.csv`
- `s93_s84_inv_rd20_h9_target28_fine2.csv`
- `s93_s84_inv_rd20_h9_target28_threshold.csv`
- `s93_s84_inv_rd20_h9_target28_threshold_worst_day.csv`
- `s93_s84_inv_rd20_h9_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S93 uses `s92_s84_inv_rd20_h10_daily.csv` as the base, so it is compared
  against the current champion S92.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`.
- Fill is simulated from `j+1` via the existing `sim_s84_backtest.run_single`
  replay.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance <= 2.0` is known at signal construction time from entry/SL,
  not from future outcome.
- `fill_hour < 9` is based on the fill timestamp available at simulated entry;
  it does not use future candle outcome.
- No future candle, same-bar close fill, or post-entry result filter is used.

## Verdict

Found new champion:

```text
S93 = S92 + INV_S84_M15_OLDWICK_FOLLOW_RD2_HBEFORE9x9.48
```

This improves both avg $/day and min $/day while keeping max losing-day streak
at 3 and passing the `-999.91` / `-1000` floors. Continue with S94 search using
S93 as the new baseline.
