# S130 Champion - Inverse S84 RD 2.0-2.7 H11-12 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

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

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin2_rd2.7_hfrom11_hbefore12
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `2.0 <= risk_distance <= 2.7`
- Time filter: `11 <= fill_hour < 12` BKK
- ไม่ซ้ำ ladder เดิม (2.0-2.7 ใช้ H12/H14/H18/H20 ไปแล้ว; H11 ของ band อื่นคนละ leg)
- Raw trades: 10/15/16/20 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
- Leg equity stats: lot_max 0.02, leg DD 0.88%, skipped 0

## New Champion

```text
S130 = S129 + INV_S84_M15_OLDWICK_FOLLOW_RD2.0_2.7_H11_12x9.007
```

| Metric | S130 |
|---|---:|
| Avg $/day | 1239.3009 |
| Min $/day | 1206.5335 |
| Min PF | 9.61930 |
| Max losing-day streak | 3 |
| Worst day | -999.90930 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10525 |

Per-window exact from `s130_s84_inv_rdmin20_rd27_h11_12_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1234.7372 | 11.09820 | 2 | -999.90825 | 10 |
| 120 | 1235.7011 | 10.87838 | 2 | -997.45850 | 15 |
| 150 | 1280.2320 | 10.80693 | 3 | -999.90896 | 16 |
| 180 | 1206.5335 | 9.61930 | 3 | -999.90930 | 20 |

## Weight Threshold

`s130_s84_inv_rdmin20_rd27_h11_12_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 9.007 | highest 0.001-step weight that passes `-999.91` |
| 9.008 | fails `-999.91` |

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
- `s130_s84_inv_rdmin20_rd27_h11_12_target28_probe.csv`
- `s130_s84_inv_rdmin20_rd27_h11_12_target28_fine.csv`
- `s130_s84_inv_rdmin20_rd27_h11_12_target28_ultrafine.csv`
- `s130_s84_inv_rdmin20_rd27_h11_12_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S130 uses `s129_s84_inv_rdmin13_rd20_h9_10_daily.csv` as the base, so it is
  compared against the current champion S129.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`; fill from `j+1` via `sim_s84_backtest.run_single`.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `11 <= fill_hour < 12` uses the simulated fill timestamp available at entry,
  not any post-entry outcome.
- No future candle, same-bar close fill, or result filter is used.

## Verdict

Found new champion:

```text
S130 = S129 + INV_S84_M15_OLDWICK_FOLLOW_RD2.0_2.7_H11_12x9.007
```

This improves avg $/day (1236.33 → 1239.30) and min $/day (1203.92 → 1206.53) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S131 search using S130 as the new baseline — เป้า $1500/วัน.
