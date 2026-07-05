# S109 Champion - Inverse S84 RD 2.7-3.4 H14-15 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S108 = S107 + INV_S84_M15_OLDWICK_FOLLOW_RD2.7_3.4_H16_17x60.391
```

| Metric | S108 |
|---|---:|
| Avg $/day | 780.1641 |
| Min $/day | 733.6726 |
| Min PF | 6.59213 |
| Max losing-day streak | 3 |
| Worst day | -999.90926 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10485 |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin2.7_rd3.4_hfrom14_hbefore15
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `2.7 <= risk_distance <= 3.4`
- Time filter: `14 <= fill_hour < 15` BKK
- Raw trades: 11/17/21/22 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
- Leg equity stats: lot_max 0.02, leg DD 2.19%, skipped 10

## New Champion

```text
S109 = S108 + INV_S84_M15_OLDWICK_FOLLOW_RD2.7_3.4_H14_15x55.179
```

| Metric | S109 |
|---|---:|
| Avg $/day | 781.5398 |
| Min $/day | 746.2963 |
| Min PF | 6.67540 |
| Max losing-day streak | 3 |
| Worst day | -999.90926 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10495 |

Per-window exact from `s109_s84_inv_rdmin27_rd34_h14_15_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 746.2963 | 6.79925 | 2 | -999.90582 | 11 |
| 120 | 795.3157 | 7.03515 | 2 | -981.88805 | 17 |
| 150 | 813.7175 | 7.03902 | 2 | -999.90926 | 21 |
| 180 | 770.8297 | 6.67540 | 3 | -999.90886 | 22 |

## Weight Threshold

`s109_s84_inv_rdmin27_rd34_h14_15_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 55.179 | highest 0.001-step weight that passes `-999.91` |
| 55.180 | fails `-999.91` |

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
- `s109_s84_inv_rdmin27_rd34_h14_15_target28_probe.csv`
- `s109_s84_inv_rdmin27_rd34_h14_15_target28_fine.csv`
- `s109_s84_inv_rdmin27_rd34_h14_15_target28_ultrafine.csv`
- `s109_s84_inv_rdmin27_rd34_h14_15_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S109 uses `s108_s84_inv_rdmin27_rd34_h16_17_daily.csv` as the base, so it is
  compared against the current champion S108.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`; fill from `j+1` via `sim_s84_backtest.run_single`.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `14 <= fill_hour < 15` uses the simulated fill timestamp available at entry,
  not any post-entry outcome.
- No future candle, same-bar close fill, or result filter is used.

## Verdict

Found new champion:

```text
S109 = S108 + INV_S84_M15_OLDWICK_FOLLOW_RD2.7_3.4_H14_15x55.179
```

This improves avg $/day (780.16 → 781.54) and min $/day (733.67 → 746.30) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S110 search using S109 as the new baseline (re-sweep ชั่วโมงที่เคย
fail ของทั้ง RD band + slice band 2.0-2.7 / 3.4-4.0).
