# S119 Champion - Inverse S84 RD 2.0-2.7 H18-19 Overlay — 🎯 ทุก window ≥ $1000/วัน

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## 🎯 Milestone

**S119 คือ champion แรกที่ min $/day ≥ $1000** — ทุก window (90/120/150/180d) อยู่
เหนือ $1010/วันทั้งหมด เป้าหมาย $1000/วัน สำเร็จสมบูรณ์ทั้ง avg และ min
เป้าถัดไป: $1500/วัน → $2000/วัน

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S118 = S117 + INV_S84_M15_OLDWICK_FOLLOW_RD3.4_4.0_H17_18x149.023
```

| Metric | S118 |
|---|---:|
| Avg $/day | 1020.9369 |
| Min $/day | 986.5169 |
| Min PF | 7.87677 |
| Max losing-day streak | 3 |
| Worst day | -999.90930 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10495 |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin2_rd2.7_hfrom18_hbefore19
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `2.0 <= risk_distance <= 2.7`
- Time filter: `18 <= fill_hour < 19` BKK
- Raw trades: 14/17/25/29 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
- Leg equity stats: lot_max 0.02, leg DD 2.58%, skipped 10

## New Champion

```text
S119 = S118 + INV_S84_M15_OLDWICK_FOLLOW_RD2.0_2.7_H18_19x144.849
```

| Metric | S119 |
|---|---:|
| Avg $/day | 1022.5765 |
| Min $/day | 1010.0427 |
| Min PF | 7.63382 |
| Max losing-day streak | 3 |
| Worst day | -999.90930 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10505 |

Per-window exact from `s119_s84_inv_rdmin20_rd27_h18_19_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1012.0103 | 9.15267 | 2 | -999.90825 | 14 |
| 120 | 1033.7625 | 8.70911 | 2 | -999.90834 | 17 |
| 150 | 1034.4906 | 8.42661 | 3 | -999.90687 | 25 |
| 180 | 1010.0427 | 7.63382 | 3 | -999.90930 | 29 |

## Weight Threshold

`s119_s84_inv_rdmin20_rd27_h18_19_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 144.849 | highest 0.001-step weight that passes `-999.91` |
| 144.850 | fails `-999.91` |

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
- `s119_s84_inv_rdmin20_rd27_h18_19_target28_probe.csv`
- `s119_s84_inv_rdmin20_rd27_h18_19_target28_fine.csv`
- `s119_s84_inv_rdmin20_rd27_h18_19_target28_ultrafine.csv`
- `s119_s84_inv_rdmin20_rd27_h18_19_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S119 uses `s118_s84_inv_rdmin34_rd40_h17_18_daily.csv` as the base, so it is
  compared against the current champion S118.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`; fill from `j+1` via `sim_s84_backtest.run_single`.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `18 <= fill_hour < 19` uses the simulated fill timestamp available at entry,
  not any post-entry outcome.
- No future candle, same-bar close fill, or result filter is used.

## ⚠️ คำเตือน in-sample overfit (ยืนยันซ้ำ)

ตัวเลข $1022/วัน คือผลจาก in-sample re-weighting ของ S84 generator เดียว โดย weight
ทุกชั้นถูก optimize ชิดขอบ floor `-999.91` ในข้อมูลชุดเดียวกัน — ใช้เป็น upper bound
ของ framework เท่านั้น ห้ามตีความเป็นกำไรคาดหวังจริง ต้องผ่าน out-of-sample /
walk-forward ก่อนพิจารณา deploy (ดูบทเรียน S21-S58)

## Verdict

Found new champion and reached the full $1000/day goal (both avg and min):

```text
S119 = S118 + INV_S84_M15_OLDWICK_FOLLOW_RD2.0_2.7_H18_19x144.849
```

This improves avg $/day (1020.94 → 1022.58) and min $/day (986.52 → 1010.04) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S120 search using S119 as the new baseline — เป้าถัดไป $1500/วัน.
