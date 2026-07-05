# S94 Champion - Post-9AM Inverse S84 RD2 Micro Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

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

## New Leg

Winning overlay:

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frd2_hfrom9
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
- Time filter: `fill_hour >= 9` BKK

## New Champion

```text
S94 = S93 + INV_S84_M15_OLDWICK_FOLLOW_RD2_HFROM9x0.002
```

| Metric | S94 |
|---|---:|
| Avg $/day | 607.9452 |
| Min $/day | 587.3522 |
| Min PF | 5.21775 |
| Max losing-day streak | 3 |
| Worst day | -999.90901 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10391 |

Per-window exact from `s94_s84_inv_rd20_hfrom9_daily.csv`:

| Window | $/day | PF | Streak | Worst day |
|---:|---:|---:|---:|---:|
| 90 | 587.3522 | 5.21775 | 3 | -978.3384 |
| 120 | 647.0709 | 5.76905 | 3 | -976.22864 |
| 150 | 607.6085 | 5.64103 | 3 | -999.90901 |
| 180 | 589.7492 | 5.31157 | 3 | -997.10707 |

Raw counts after `risk_distance <= 2.0` and `fill_hour >= 9`:

| Window | Raw trades |
|---:|---:|
| 90 | 76 |
| 120 | 105 |
| 150 | 178 |
| 180 | 219 |

## Weight Threshold

`s94_s84_inv_rd20_hfrom9_target28_ultramicro.csv`:

| Weight | Avg $/day | Min $/day | Streak | Worst day | Floor -999.91 |
|---:|---:|---:|---:|---:|---|
| 0.002 | 607.9452 | 587.3522 | 3 | -999.90901 | PASS |
| 0.003 | ~607.95 | ~587.35 | 3 | below -999.91 | FAIL |

`x0.002` is the highest tested 0.001-step weight that keeps the `-999.91`
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
- `s94_s84_inv_rd20_h8_target28_probe.csv`
- `s94_s84_inv_rd20_hfrom9_target28_probe.csv`
- `s94_s84_inv_rd20_hfrom9_target28_micro.csv`
- `s94_s84_inv_rd20_hfrom9_target28_ultramicro.csv`
- `s94_s84_inv_rd20_hfrom9_target28_ultramicro_worst_day.csv`
- `s94_s84_inv_rd20_hfrom9_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S94 uses `s93_s84_inv_rd20_h9_daily.csv` as the base, so it is compared
  against the current champion S93.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`.
- Fill is simulated from `j+1` via the existing `sim_s84_backtest.run_single`
  replay.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance <= 2.0` is known at signal construction time from entry/SL,
  not from future outcome.
- `fill_hour >= 9` is based on the fill timestamp available at simulated entry;
  it does not use future candle outcome.
- No future candle, same-bar close fill, or post-entry result filter is used.

## Verdict

Found new micro champion:

```text
S94 = S93 + INV_S84_M15_OLDWICK_FOLLOW_RD2_HFROM9x0.002
```

This improves both avg $/day and min $/day while keeping max losing-day streak
at 3 and passing the `-999.91` / `-1000` floors. Continue with S95 search using
S94 as the new baseline.
