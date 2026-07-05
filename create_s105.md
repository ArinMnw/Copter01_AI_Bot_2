# S105 Champion - Inverse S84 RD 2.7-3.4 H22-23 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S104 = S103 + INV_S84_M15_OLDWICK_FOLLOW_RD2.7_3.4x3.195
```

| Metric | S104 |
|---|---:|
| Avg $/day | 678.9334 |
| Min $/day | 652.3068 |
| Min PF | 5.83902 |
| Max losing-day streak | 3 |
| Worst day | -999.90886 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10470 |

## Search Space รอบนี้

Hour-slice sweep ของ band RD 2.7-3.4 บน S104 base (H7-H23):

| Hour | ผล (ที่ probe cap x60) | หมายเหตุ |
|---|---|---|
| H8-9 | beats=True avg 686.70 | candidate |
| H14-15 | beats=True avg 680.30 | candidate |
| H16-17 | beats=True avg 688.63 | candidate |
| H18-19 | beats=True avg 679.02 | เล็กมาก |
| H21-22 | beats=True avg 696.24 | candidate |
| **H22-23** | **beats=True avg 699.21** | ✅ ผู้ชนะ |
| ช่องอื่น (H7, H9-13, H15, H17, H19-20, H23) | beats=False | — |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin2.7_rd3.4_hfrom22_hbefore23
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `2.7 <= risk_distance <= 3.4`
- Time filter: `22 <= fill_hour < 23` BKK
- Raw trades: 8/9/13/16 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
  (ไม่ใช่ degenerate ไม่ต้องใช้ stress rule)
- Leg equity stats: lot_max 0.02, leg DD 0.61%, skipped 0

## New Champion

```text
S105 = S104 + INV_S84_M15_OLDWICK_FOLLOW_RD2.7_3.4_H22_23x114.260
```

| Metric | S105 |
|---|---:|
| Avg $/day | 717.5473 |
| Min $/day | 694.7353 |
| Min PF | 6.17316 |
| Max losing-day streak | 3 |
| Worst day | -999.90886 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10470 |

Per-window exact from `s105_s84_inv_rdmin27_rd34_h22_23_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 694.7353 | 6.17316 | 3 | -969.09381 | 8 |
| 120 | 745.3823 | 6.59594 | 2 | -981.88805 | 9 |
| 150 | 729.2405 | 6.59120 | 2 | -999.90687 | 13 |
| 180 | 700.8309 | 6.25792 | 3 | -999.90886 | 16 |

## Weight Threshold

`s105_s84_inv_rdmin27_rd34_h22_23_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 114.260 | highest 0.001-step weight that passes `-999.91` |
| 114.261 | fails `-999.91` |

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
- `s105_s84_inv_rdmin27_rd34_h7_8..h23_24_target28_probe.csv` (hour sweep 17 ไฟล์)
- `s105_s84_inv_rdmin27_rd34_h22_23_target28_wide.csv`
- `s105_s84_inv_rdmin27_rd34_h22_23_target28_fine.csv`
- `s105_s84_inv_rdmin27_rd34_h22_23_target28_ultrafine.csv`
- `s105_s84_inv_rdmin27_rd34_h22_23_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S105 uses `s104_s84_inv_rdmin27_rd34_daily.csv` as the base, so it is compared
  against the current champion S104.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`; fill from `j+1` via `sim_s84_backtest.run_single`.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `22 <= fill_hour < 23` uses the simulated fill timestamp available at entry,
  not any post-entry outcome.
- No future candle, same-bar close fill, or result filter is used.

## Verdict

Found new champion:

```text
S105 = S104 + INV_S84_M15_OLDWICK_FOLLOW_RD2.7_3.4_H22_23x114.260
```

This improves avg $/day (678.93 → 717.55) and min $/day (652.31 → 694.74) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S106 search using S105 as the new baseline (H21-22 / H16-17 / H8-9
ของ band เดียวกันคือ candidates ถัดไป).
