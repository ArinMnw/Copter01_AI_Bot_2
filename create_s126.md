# S126 Champion - Inverse S84 RD 1.3-2.0 H13-14 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

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

## Search Space รอบนี้

Batch sweep 7 band × 24 hour บน S125 base — Top ที่เหลือส่วนใหญ่เป็น repeats
(1.3-2.0 H20=S103, 2.0-2.7 H14=S110, 4.0-5.0 H22=S124, 3.4-4.0 H20=S113,
3.4-4.0 H19=S114, 2.7-3.4 H8=S107, **1.3-2.0 H18=S99 จาก ladder ก่อน S103**,
2.0-2.7 H12=S120, 2.7-3.4 H16=S108, 1.3-2.0 H10=S116):

| Band | Hour | Best w | avg | min | หมายเหตุ |
|---|---|---:|---:|---:|---|
| **1.3-2.0** | **H13** | **26** | **1226.71** | **1167.89** | ✅ ผู้ชนะ (leg ใหม่จริง — H13 ไม่อยู่ใน S96 H10-13 ที่คลุมแค่ 10,11,12) |
| 3.4-4.0 | H8 | 46 | 1225.31 | 1167.14 | candidate รอบถัดไป |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin1.3_rd2_hfrom13_hbefore14
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `1.3 <= risk_distance <= 2.0`
- Time filter: `13 <= fill_hour < 14` BKK
- Raw trades: 8/10/15/16 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
- Leg equity stats: lot_max 0.04, leg DD 1.05%, skipped 0

## New Champion

```text
S126 = S125 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0_H13_14x27.964
```

| Metric | S126 |
|---|---:|
| Avg $/day | 1227.0836 |
| Min $/day | 1168.3346 |
| Min PF | 9.12236 |
| Max losing-day streak | 3 |
| Worst day | -999.90930 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10525 |

Per-window exact from `s126_s84_inv_rdmin13_rd20_h13_14_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1253.3018 | 12.01709 | 2 | -999.90825 | 8 |
| 120 | 1245.8941 | 11.36742 | 2 | -999.90834 | 10 |
| 150 | 1240.8040 | 10.73116 | 3 | -999.90687 | 15 |
| 180 | 1168.3346 | 9.12236 | 3 | -999.90930 | 16 |

## Weight Threshold

`s126_s84_inv_rdmin13_rd20_h13_14_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 27.964 | highest 0.001-step weight that passes `-999.91` |
| 27.965 | fails `-999.91` |

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
- `s126_s84_inv_rdmin13_rd20_h13_14_target28_probe.csv`
- `s126_s84_inv_rdmin13_rd20_h13_14_target28_fine.csv`
- `s126_s84_inv_rdmin13_rd20_h13_14_target28_ultrafine.csv`
- `s126_s84_inv_rdmin13_rd20_h13_14_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S126 uses `s125_s84_inv_rdmin40_rd50_h20_21_daily.csv` as the base, so it is
  compared against the current champion S125.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`; fill from `j+1` via `sim_s84_backtest.run_single`.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `13 <= fill_hour < 14` uses the simulated fill timestamp available at entry,
  not any post-entry outcome.
- No future candle, same-bar close fill, or result filter is used.

## Verdict

Found new champion:

```text
S126 = S125 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0_H13_14x27.964
```

This improves avg $/day (1221.73 → 1227.08) and min $/day (1162.01 → 1168.33) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S127 search using S126 as the new baseline (3.4-4.0 H8 คือ candidate
ถัดไป) — เป้า $1500/วัน.
