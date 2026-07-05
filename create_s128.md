# S128 Champion - Inverse S84 RD 0.8-1.3 H11-12 Overlay (เปิด band ใหม่)

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S127 = S126 + INV_S84_M15_OLDWICK_FOLLOW_RD3.4_4.0_H8_9x46.180
```

| Metric | S127 |
|---|---:|
| Avg $/day | 1230.6751 |
| Min $/day | 1173.4836 |
| Min PF | 9.25519 |
| Max losing-day streak | 3 |
| Worst day | -999.90930 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10525 |

## Search Space รอบนี้

Batch sweep 7 band × 24 hour บน S127 base — Top ส่วนใหญ่เป็น repeats (S103, S110,
S124, S113, S99, S114, S107, S126, S116, S100) เหลือ leg ใหม่:

| Band | Hour | Best w | avg | min | หมายเหตุ |
|---|---|---:|---:|---:|---|
| **0.8-1.3** | **H11** | **436** | **1233.57** | **1197.39** | ✅ ผู้ชนะ (band ใหม่, min +24) |
| 1.3-2.0 | H9 | 52 | 1233.41 | 1179.92 | candidate รอบถัดไป |
| 2.0-2.7 | H11 | 8 | 1233.31 | 1175.80 | candidate |
| 2.0-2.7 | H13 | 26 | 1233.06 | 1175.43 | candidate |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin0.8_rd1.3_hfrom11_hbefore12
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `0.8 <= risk_distance <= 1.3`
- Time filter: `11 <= fill_hour < 12` BKK
- Raw trades: 1/1/5/5 ที่ 90/120/150/180d — เบาบางแต่มีวันติดลบจริง floor bind ปกติ
  (best w 436 < grid cap 600) ⚠️ 90/120d มีไม้เดียว — ความเชื่อมั่นต่ำกว่า leg อื่น
- Leg equity stats: lot_max 0.05, leg DD 0.60%, skipped 0

## New Champion

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

Per-window exact from `s128_s84_inv_rdmin08_rd13_h11_12_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1231.4578 | 11.30704 | 2 | -999.90825 | 1 |
| 120 | 1230.7617 | 11.00907 | 2 | -999.90834 | 1 |
| 150 | 1274.6414 | 10.89305 | 3 | -999.90896 | 5 |
| 180 | 1197.4149 | 9.47124 | 3 | -999.90930 | 5 |

## Weight Threshold

`s128_s84_inv_rdmin08_rd13_h11_12_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 436.437 | highest 0.001-step weight that passes `-999.91` |
| 436.438 | fails `-999.91` |

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
- `s128_s84_inv_rdmin08_rd13_h11_12_target28_probe.csv`
- `s128_s84_inv_rdmin08_rd13_h11_12_target28_fine.csv`
- `s128_s84_inv_rdmin08_rd13_h11_12_target28_ultrafine.csv`
- `s128_s84_inv_rdmin08_rd13_h11_12_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S128 uses `s127_s84_inv_rdmin34_rd40_h8_9_daily.csv` as the base, so it is
  compared against the current champion S127.
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
S128 = S127 + INV_S84_M15_OLDWICK_FOLLOW_RD0.8_1.3_H11_12x436.437
```

This improves avg $/day (1230.68 → 1233.57) and min $/day (1173.48 → 1197.41) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S129 search using S128 as the new baseline (1.3-2.0 H9 / 2.0-2.7
H11+H13 คือ candidates ถัดไป) — เป้า $1500/วัน.
