# S106 Champion - Inverse S84 RD 2.7-3.4 H21-22 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

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

## Search Space รอบนี้

Re-probe hour candidates ที่เหลือของ band RD 2.7-3.4 บน S105 base:

| Hour | ผล (probe grid 0:300:2) | หมายเหตุ |
|---|---|---|
| H8-9 | beats=True x86 avg 728.68 | candidate |
| H14-15 | beats=True x54 avg 718.89 | candidate |
| H16-17 | beats=True x60 avg 727.25 | candidate |
| H18-19 | beats=False | ตกรอบ |
| **H21-22** | **beats=True x144 avg 759.08** | ✅ ผู้ชนะ |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin2.7_rd3.4_hfrom21_hbefore22
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `2.7 <= risk_distance <= 3.4`
- Time filter: `21 <= fill_hour < 22` BKK
- Raw trades: 4/5/10/12 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
- Leg equity stats: lot_max 0.02, leg DD 0.54%, skipped 0

## New Champion

```text
S106 = S105 + INV_S84_M15_OLDWICK_FOLLOW_RD2.7_3.4_H21_22x144.488
```

| Metric | S106 |
|---|---:|
| Avg $/day | 759.2200 |
| Min $/day | 730.3757 |
| Min PF | 6.51660 |
| Max losing-day streak | 3 |
| Worst day | -999.90886 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10470 |

Per-window exact from `s106_s84_inv_rdmin27_rd34_h21_22_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 730.3757 | 6.55280 | 2 | -969.09381 | 4 |
| 120 | 778.8313 | 7.10662 | 2 | -981.88805 | 5 |
| 150 | 783.4717 | 7.20470 | 2 | -999.90687 | 10 |
| 180 | 744.2014 | 6.51660 | 3 | -999.90886 | 12 |

## Weight Threshold

`s106_s84_inv_rdmin27_rd34_h21_22_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 144.488 | highest 0.001-step weight that passes `-999.91` |
| 144.489 | fails `-999.91` |

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
- `s106_s84_inv_rdmin27_rd34_h8_9 / h14_15 / h16_17 / h18_19 / h21_22 _target28_probe.csv`
- `s106_s84_inv_rdmin27_rd34_h21_22_target28_fine.csv`
- `s106_s84_inv_rdmin27_rd34_h21_22_target28_ultrafine.csv`
- `s106_s84_inv_rdmin27_rd34_h21_22_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S106 uses `s105_s84_inv_rdmin27_rd34_h22_23_daily.csv` as the base, so it is
  compared against the current champion S105.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`; fill from `j+1` via `sim_s84_backtest.run_single`.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `21 <= fill_hour < 22` uses the simulated fill timestamp available at entry,
  not any post-entry outcome.
- No future candle, same-bar close fill, or result filter is used.

## Verdict

Found new champion:

```text
S106 = S105 + INV_S84_M15_OLDWICK_FOLLOW_RD2.7_3.4_H21_22x144.488
```

This improves avg $/day (717.55 → 759.22) and min $/day (694.74 → 730.38) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S107 search using S106 as the new baseline (H8-9 / H14-15 / H16-17
ของ band เดียวกันคือ candidates ถัดไป).
