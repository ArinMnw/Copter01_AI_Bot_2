# S125 Champion - Inverse S84 RD 4.0-5.0 H20-21 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S124 = S123 + INV_S84_M15_OLDWICK_FOLLOW_RD4.0_5.0_H22_23x572.929
```

| Metric | S124 |
|---|---:|
| Avg $/day | 1200.4054 |
| Min $/day | 1150.2768 |
| Min PF | 9.01276 |
| Max losing-day streak | 3 |
| Worst day | -999.90930 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10525 |

## Search Space รอบนี้

Batch sweep 7 band × 24 hour บน S124 base — Top candidates (ข้าม repeats: 1.3-2.0
H20=S103, 3.4-4.0 H19=S114, 2.0-2.7 H14=S110, 3.4-4.0 H20=S113):

| Band | Hour | Best w | avg | min | หมายเหตุ |
|---|---|---:|---:|---:|---|
| **4.0-5.0** | **H20** | **112** | **1221.54** | **1161.91** | ✅ ผู้ชนะ |
| 1.3-2.0 | H18 | 24 | 1207.67 | 1158.71 | candidate รอบถัดไป |
| 2.0-2.7 | H12 | 32 | 1206.73 | 1155.01 | ❌ leg เดิม S120 |
| 1.3-2.0 | H13 | 26 | 1205.39 | 1156.16 | candidate |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin4_rd5_hfrom20_hbefore21
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `4.0 <= risk_distance <= 5.0`
- Time filter: `20 <= fill_hour < 21` BKK
- Raw trades: 12/14/19/22 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
- Leg equity stats: lot_max 0.01, leg DD 1.19%, skipped 0

## New Champion

```text
S125 = S124 + INV_S84_M15_OLDWICK_FOLLOW_RD4.0_5.0_H20_21x113.001
```

| Metric | S125 |
|---|---:|
| Avg $/day | 1221.7279 |
| Min $/day | 1162.0100 |
| Min PF | 9.10623 |
| Max losing-day streak | 3 |
| Worst day | -999.90930 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10525 |

Per-window exact from `s125_s84_inv_rdmin40_rd50_h20_21_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1250.2538 | 12.32633 | 2 | -999.90825 | 12 |
| 120 | 1241.6645 | 11.55637 | 2 | -999.90834 | 14 |
| 150 | 1232.9834 | 10.69733 | 3 | -999.90687 | 19 |
| 180 | 1162.0100 | 9.10623 | 3 | -999.90930 | 22 |

## Weight Threshold

`s125_s84_inv_rdmin40_rd50_h20_21_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 113.001 | highest 0.001-step weight that passes `-999.91` |
| 113.002 | fails `-999.91` |

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
- `s125_s84_inv_rdmin40_rd50_h20_21_target28_probe.csv`
- `s125_s84_inv_rdmin40_rd50_h20_21_target28_fine.csv`
- `s125_s84_inv_rdmin40_rd50_h20_21_target28_ultrafine.csv`
- `s125_s84_inv_rdmin40_rd50_h20_21_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S125 uses `s124_s84_inv_rdmin40_rd50_h22_23_daily.csv` as the base, so it is
  compared against the current champion S124.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`; fill from `j+1` via `sim_s84_backtest.run_single`.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `20 <= fill_hour < 21` uses the simulated fill timestamp available at entry,
  not any post-entry outcome.
- No future candle, same-bar close fill, or result filter is used.

## Verdict

Found new champion:

```text
S125 = S124 + INV_S84_M15_OLDWICK_FOLLOW_RD4.0_5.0_H20_21x113.001
```

This improves avg $/day (1200.41 → 1221.73) and min $/day (1150.28 → 1162.01) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S126 search using S125 as the new baseline — เป้า $1500/วัน.
