# S129 Champion - Inverse S84 RD 1.3-2.0 H9-10 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S128 = S127 + INV_S84_M15_OLDWICK_FOLLOW_RD0.8_1.3_H11_12x436.437
```

| Metric | S128 |
|---|---:|
| Avg $/day | 1233.5690 |
| Min $/day | 1197.4149 |
| Min PF | 9.47124 |
| Max losing-day streak | 3 |
| Worst day | -999.90930 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10525 |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin1.3_rd2_hfrom9_hbefore10
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `1.3 <= risk_distance <= 2.0`
- Time filter: `9 <= fill_hour < 10` BKK
- หมายเหตุ: ช่องนี้เคย probe ไม่ผ่านตอน S103 stage (base เก่า) — ผ่านได้บน base
  ปัจจุบันเพราะโครงสร้าง 90d window เปลี่ยน ไม่ซ้ำกับ leg ใดใน ladder
- Raw trades: 2/3/4/7 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
- Leg equity stats: lot_max 0.04, leg DD 0.56%, skipped 0

## New Champion

```text
S129 = S128 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0_H9_10x52.566
```

| Metric | S129 |
|---|---:|
| Avg $/day | 1236.3290 |
| Min $/day | 1203.9214 |
| Min PF | 9.58842 |
| Max losing-day streak | 3 |
| Worst day | -999.90930 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10525 |

Per-window exact from `s129_s84_inv_rdmin13_rd20_h9_10_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1231.1424 | 11.02792 | 2 | -999.90825 | 2 |
| 120 | 1232.6672 | 10.82712 | 2 | -999.90834 | 3 |
| 150 | 1277.5851 | 10.76608 | 3 | -999.90896 | 4 |
| 180 | 1203.9214 | 9.58842 | 3 | -999.90930 | 7 |

## Weight Threshold

`s129_s84_inv_rdmin13_rd20_h9_10_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 52.566 | highest 0.001-step weight that passes `-999.91` |
| 52.567 | fails `-999.91` |

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
- `s129_s84_inv_rdmin13_rd20_h9_10_target28_probe.csv`
- `s129_s84_inv_rdmin13_rd20_h9_10_target28_fine.csv`
- `s129_s84_inv_rdmin13_rd20_h9_10_target28_ultrafine.csv`
- `s129_s84_inv_rdmin13_rd20_h9_10_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S129 uses `s128_s84_inv_rdmin08_rd13_h11_12_daily.csv` as the base, so it is
  compared against the current champion S128.
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
S129 = S128 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0_H9_10x52.566
```

This improves avg $/day (1233.57 → 1236.33) and min $/day (1197.41 → 1203.92) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S130 search using S129 as the new baseline — เป้า $1500/วัน.
