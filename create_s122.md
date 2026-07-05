# S122 Champion - Inverse S84 RD 2.7-3.4 H9-10 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S121 = S120 + INV_S84_M15_OLDWICK_FOLLOW_RD2.7_3.4_H20_21x30.194
```

| Metric | S121 |
|---|---:|
| Avg $/day | 1049.0123 |
| Min $/day | 1029.5931 |
| Min PF | 8.40086 |
| Max losing-day streak | 3 |
| Worst day | -999.90930 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10505 |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin2.7_rd3.4_hfrom9_hbefore10
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `2.7 <= risk_distance <= 3.4`
- Time filter: `9 <= fill_hour < 10` BKK
- Raw trades: 16/19/20/24 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
- Leg equity stats: lot_max 0.02, leg DD 1.77%, skipped 10

## New Champion

```text
S122 = S121 + INV_S84_M15_OLDWICK_FOLLOW_RD2.7_3.4_H9_10x74.771
```

| Metric | S122 |
|---|---:|
| Avg $/day | 1053.4931 |
| Min $/day | 1041.8888 |
| Min PF | 8.45319 |
| Max losing-day streak | 3 |
| Worst day | -999.90930 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10515 |

Per-window exact from `s122_s84_inv_rdmin27_rd34_h9_10_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1046.9368 | 10.54426 | 2 | -999.90825 | 16 |
| 120 | 1064.8528 | 9.67275 | 2 | -999.90834 | 19 |
| 150 | 1060.2943 | 9.27838 | 3 | -999.90687 | 20 |
| 180 | 1041.8888 | 8.45319 | 3 | -999.90930 | 24 |

## Weight Threshold

`s122_s84_inv_rdmin27_rd34_h9_10_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 74.771 | highest 0.001-step weight that passes `-999.91` |
| 74.772 | fails `-999.91` |

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
- `s122_s84_inv_rdmin27_rd34_h9_10_target28_probe.csv`
- `s122_s84_inv_rdmin27_rd34_h9_10_target28_fine.csv`
- `s122_s84_inv_rdmin27_rd34_h9_10_target28_ultrafine.csv`
- `s122_s84_inv_rdmin27_rd34_h9_10_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S122 uses `s121_s84_inv_rdmin27_rd34_h20_21_daily.csv` as the base, so it is
  compared against the current champion S121.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`; fill from `j+1` via `sim_s84_backtest.run_single`.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `9 <= fill_hour < 10` uses the simulated fill timestamp available at entry,
  not any post-entry outcome.
- No future candle, same-bar close fill, or result filter is used.

## Verdict

Found new champion:

```text
S122 = S121 + INV_S84_M15_OLDWICK_FOLLOW_RD2.7_3.4_H9_10x74.771
```

This improves avg $/day (1049.01 → 1053.49) and min $/day (1029.59 → 1041.89) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S123 search using S122 as the new baseline — จะเปิด search space ใหม่
(RD band 4.0-5.0 / 0.8-1.3 ฯลฯ) ควบคู่กับ band เดิมที่เหลือ.
