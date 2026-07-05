# S102 Champion - Inverse S84 RD 1.3-2.0 Afternoon Micro Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S101 = S100 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0_H14_15x23.731
```

| Metric | S101 |
|---|---:|
| Avg $/day | 652.8490 |
| Min $/day | 629.1864 |
| Min PF | 5.57517 |
| Max losing-day streak | 3 |
| Worst day | -999.90785 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10391 |

## New Leg

Winning overlay:

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin1.3_rd2_hfrom15_hbefore16
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
- Time filter: `15 <= fill_hour < 16` BKK

## New Champion

```text
S102 = S101 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0_H15_16x2.918
```

| Metric | S102 |
|---|---:|
| Avg $/day | 652.9061 |
| Min $/day | 629.2306 |
| Min PF | 5.57738 |
| Max losing-day streak | 3 |
| Worst day | -999.90785 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10391 |

Per-window exact from `s102_s84_inv_rdmin13_rd20_h15_16_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 636.5458 | 5.65676 | 3 | -987.11361 | 2 |
| 120 | 690.0561 | 6.11020 | 3 | -999.90785 | 2 |
| 150 | 655.7919 | 6.09227 | 3 | -986.25864 | 6 |
| 180 | 629.2306 | 5.57738 | 3 | -999.90703 | 7 |

## Weight Threshold

`s102_s84_inv_rdmin13_rd20_h15_16_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 2.918 | highest 0.001-step weight that passes `-999.91` |
| 2.919 | fails `-999.91` |
| 2.930 | passes only `-1000`, fails `-999.91` |

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
- `s102_s84_inv_rdmin13_rd20_h15_16_target28_probe.csv`
- `s102_s84_inv_rdmin13_rd20_h15_16_target28_probe_worst_day.csv`
- `s102_s84_inv_rdmin13_rd20_h13_14_target28_probe.csv`
- `s102_s84_inv_rdmin13_rd20_h13_14_target28_probe_worst_day.csv`
- `s102_s84_inv_rdmin13_rd20_h16_17_target28_probe.csv`
- `s102_s84_inv_rdmin13_rd20_h16_17_target28_probe_worst_day.csv`
- `s102_s84_inv_rdmin13_rd20_h15_16_target28_fine.csv`
- `s102_s84_inv_rdmin13_rd20_h15_16_target28_fine_worst_day.csv`
- `s102_s84_inv_rdmin13_rd20_h15_16_target28_ultrafine.csv`
- `s102_s84_inv_rdmin13_rd20_h15_16_target28_ultrafine_worst_day.csv`
- `s102_s84_inv_rdmin13_rd20_h15_16_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S102 uses `s101_s84_inv_rdmin13_rd20_h14_15_daily.csv` as the base, so it is
  compared against the current champion S101.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`.
- Fill is simulated from `j+1` via the existing `sim_s84_backtest.run_single`
  replay.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `15 <= fill_hour < 16` uses the simulated fill timestamp available at entry,
  not any post-entry outcome.
- No future candle, same-bar close fill, or result filter is used.

## Verdict

Found new champion:

```text
S102 = S101 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0_H15_16x2.918
```

This improves both avg $/day and min $/day while keeping max losing-day streak
at 3 and passing the `-999.91` / `-1000` floors. Continue with S103 search using
S102 as the new baseline.
