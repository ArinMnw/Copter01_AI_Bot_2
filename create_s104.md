# S104 Champion - Inverse S84 RD 2.7-3.4 Whole-Day Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S103 = S102 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0_H20_21x100.563
```

| Metric | S103 |
|---|---:|
| Avg $/day | 673.4029 |
| Min $/day | 647.5072 |
| Min PF | 5.73695 |
| Max losing-day streak | 3 |
| Worst day | -999.90785 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10391 |

## Search Space รอบนี้

Hour-slice ของ RD1.3-2.0 หมดพื้นที่แล้ว (H22-23 มีไม้เฉพาะ 150/180d → min $/day ที่
90d ขยับไม่ได้ = beats ไม่ผ่าน) จึงขยายไป **RD band ใหม่ที่ยังไม่เคยถูก slice**:

| Band (whole-day) | ผลบน S103 base | หมายเหตุ |
|---|---|---|
| RD 0.5-1.0 | beats=False | avg ขึ้นแต่ min ไม่ขยับ |
| RD 1.0-1.3 | beats=False | weight ดีสุด = 0 |
| RD 2.0-2.7 | beats=False | weight ดีสุด = 0 |
| **RD 2.7-3.4** | **beats=True x3** | ✅ ผู้ชนะ |
| RD 3.4-4.0 | beats=False | weight ดีสุด = 0 |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin2.7_rd3.4
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `2.7 <= risk_distance <= 3.4`
- ไม่มี time filter (ทั้งวัน)
- Raw trades: 175/215/280/334 ที่ 90/120/150/180d — **ไม่ใช่ degenerate leg**
  (มีทั้งวันบวกและวันลบ floor bind ตามปกติ ไม่ต้องใช้ stress rule แบบ S103)
- Leg equity stats: lot_max 0.02, leg DD 5.07%, skipped by circuit breaker 79

## New Champion

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

Per-window exact from `s104_s84_inv_rdmin27_rd34_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 652.3068 | 5.83902 | 3 | -969.09381 | 175 |
| 120 | 707.6575 | 6.35153 | 3 | -981.88805 | 215 |
| 150 | 690.3464 | 6.47429 | 3 | -966.00234 | 280 |
| 180 | 665.4230 | 6.01435 | 3 | -999.90886 | 334 |

## Weight Threshold

`s104_s84_inv_rdmin27_rd34_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 3.195 | highest 0.001-step weight that passes `-999.91` |
| 3.196 | fails `-999.91` |

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
- `s104_s84_inv_rdmin27_rd34_target28_probe.csv` (+ RD 0.5-1.0 / 1.0-1.3 / 2.0-2.7 /
  3.4-4.0 probe files)
- `s104_s84_inv_rdmin27_rd34_target28_fine.csv`
- `s104_s84_inv_rdmin27_rd34_target28_ultrafine.csv`
- `s104_s84_inv_rdmin27_rd34_target28_ultrafine_worst_day.csv`
- `s104_s84_inv_rdmin27_rd34_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S104 uses `s103_s84_inv_rdmin13_rd20_h20_21_daily.csv` as the base, so it is
  compared against the current champion S103.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`; fill from `j+1` via `sim_s84_backtest.run_single`.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time —
  the RD 2.7-3.4 band ใช้ข้อมูล ณ ตอนวาง order เท่านั้น
- No future candle, same-bar close fill, or result filter is used.

## Verdict

Found new champion:

```text
S104 = S103 + INV_S84_M15_OLDWICK_FOLLOW_RD2.7_3.4x3.195
```

This improves avg $/day (673.40 → 678.93) and min $/day (647.51 → 652.31) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S105 search using S104 as the new baseline (hour slices ของ RD2.7-3.4
คือ candidate ถัดไป).
