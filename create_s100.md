# S100 Champion - Inverse S84 RD 1.3-2.0 Night Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S99 = S98 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0_H18_19x4.543
```

| Metric | S99 |
|---|---:|
| Avg $/day | 632.9161 |
| Min $/day | 611.7877 |
| Min PF | 5.42302 |
| Max losing-day streak | 3 |
| Worst day | -999.90785 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10391 |

## New Leg

Winning overlay:

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin1.3_rd2_hfrom19_hbefore20
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
- Time filter: `19 <= fill_hour < 20` BKK

## New Champion

```text
S100 = S99 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0_H19_20x58.923
```

| Metric | S100 |
|---|---:|
| Avg $/day | 645.8813 |
| Min $/day | 622.3914 |
| Min PF | 5.44798 |
| Max losing-day streak | 3 |
| Worst day | -999.90785 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10391 |

Per-window exact from `s100_s84_inv_rdmin13_rd20_h19_20_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 629.3664 | 5.52953 | 3 | -987.11361 | 8 |
| 120 | 683.6511 | 6.03578 | 3 | -999.90785 | 8 |
| 150 | 648.1165 | 5.97641 | 3 | -986.25864 | 9 |
| 180 | 622.3914 | 5.44798 | 3 | -999.90624 | 11 |

## Weight Threshold

`s100_s84_inv_rdmin13_rd20_h19_20_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 58.923 | highest 0.001-step weight that passes `-999.91` |
| 58.924 | fails `-999.91` |
| 58.939 | passes only `-1000`, fails `-999.91` |

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
- `s100_s84_inv_rdmin13_rd20_h7_8_target28_probe.csv`
- `s100_s84_inv_rdmin13_rd20_h13_14_target28_probe.csv`
- `s100_s84_inv_rdmin13_rd20_h19_20_target28_probe.csv`
- `s100_s84_inv_rdmin13_rd20_h19_20_target28_wide.csv`
- `s100_s84_inv_rdmin13_rd20_h19_20_target28_fine.csv`
- `s100_s84_inv_rdmin13_rd20_h19_20_target28_ultrafine.csv`
- `s100_s84_inv_rdmin13_rd20_h19_20_target28_ultrafine_worst_day.csv`
- `s100_s84_inv_rdmin13_rd20_h19_20_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S100 uses `s99_s84_inv_rdmin13_rd20_h18_19_daily.csv` as the base, so it is
  compared against the current champion S99.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`.
- Fill is simulated from `j+1` via the existing `sim_s84_backtest.run_single`
  replay.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `19 <= fill_hour < 20` uses the simulated fill timestamp available at entry,
  not any post-entry outcome.
- No future candle, same-bar close fill, or result filter is used.

## Verdict

Found new champion:

```text
S100 = S99 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0_H19_20x58.923
```

This improves both avg $/day and min $/day while keeping max losing-day streak
at 3 and passing the `-999.91` / `-1000` floors. Continue with S101 search using
S100 as the new baseline.
