# S95 Champion - Inverse S84 RD 1.3-2.0 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

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

## Runner Update

Added a research-only post-filter to `optimize_s88_allin4s_fast.py`:

```text
--risk-distance-min
```

This filter is applied to `risk_distance`, which is known when the simulated
entry and SL are constructed. It does not use trade outcome or future candles.

## New Leg

Winning overlay:

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin1.3_rd2
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
- Post-filter: `1.3 <= risk_distance <= 2.0`

## New Champion

```text
S95 = S94 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0x5.403
```

| Metric | S95 |
|---|---:|
| Avg $/day | 619.5492 |
| Min $/day | 599.7833 |
| Min PF | 5.32770 |
| Max losing-day streak | 3 |
| Worst day | -999.90644 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10391 |

Per-window exact from `s95_s84_inv_rdmin13_rd20_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 599.7833 | 5.32770 | 3 | -978.3384 | 83 |
| 120 | 657.4123 | 5.84465 | 3 | -976.22864 | 108 |
| 150 | 619.9587 | 5.73797 | 3 | -986.25864 | 161 |
| 180 | 601.0426 | 5.39090 | 3 | -999.90644 | 199 |

## Weight Threshold

`s95_s84_inv_rdmin13_rd20_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 5.403 | highest 0.001-step weight that passes `-999.91` |
| 5.404 | fails `-999.91` |
| 5.410 | passes only `-1000`, fails `-999.91` |

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
- `s95_s84_inv_rdmin13_rd20_target28_probe.csv`
- `s95_s84_inv_rdmin13_rd20_target28_wide.csv`
- `s95_s84_inv_rdmin13_rd20_target28_fine.csv`
- `s95_s84_inv_rdmin13_rd20_target28_ultrafine.csv`
- `s95_s84_inv_rdmin13_rd20_target28_ultrafine_worst_day.csv`
- `s95_s84_inv_rdmin13_rd20_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S95 uses `s94_s84_inv_rd20_hfrom9_daily.csv` as the base, so it is compared
  against the current champion S94.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`.
- Fill is simulated from `j+1` via the existing `sim_s84_backtest.run_single`
  replay.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `1.3 <= risk_distance <= 2.0` does not inspect outcome, TP/SL result, or any
  future candle.

## Verdict

Found new champion:

```text
S95 = S94 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0x5.403
```

This improves both avg $/day and min $/day while keeping max losing-day streak
at 3 and passing the `-999.91` / `-1000` floors. Continue with S96 search using
S95 as the new baseline.
