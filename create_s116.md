# S116 Champion - Inverse S84 RD 1.3-2.0 H10-11 Overlay — 🎯 ทะลุเป้า $1000/วัน

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## 🎯 Milestone

**S116 คือ champion แรกของ ladder ที่ avg $/day ≥ $1000** (เป้าหมายที่ตั้งไว้)
- avg $/day = 1005.79 (windows 120/150/180 ทะลุ $1000 ทุกอัน, 90d = 963.21)
- เป้าถัดไป: min window ≥ $1000 → $1500/วัน → $2000/วัน

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S115 = S114 + INV_S84_M15_OLDWICK_FOLLOW_RD2.0_2.7_H20_21x206.912
```

| Metric | S115 |
|---|---:|
| Avg $/day | 980.0725 |
| Min $/day | 935.4516 |
| Min PF | 8.01968 |
| Max losing-day streak | 3 |
| Worst day | -999.90926 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10495 |

## Search Space รอบนี้

Batch sweep ทุก band × hour บน S115 base — Top candidates:

| Band | Hour | Best w | avg | min | หมายเหตุ |
|---|---|---:|---:|---:|---|
| 1.3-2.0 | H20 | 300 (cap) | 1041.22 | 968.15 | ❌ ข้าม — S103 degenerate leg |
| **1.3-2.0** | **H10** | **172** | **1005.73** | **963.14** | ✅ ผู้ชนะ |
| 3.4-4.0 | H19 | 254 | 1005.20 | 944.00 | ❌ ข้าม — leg เดิม S114 (weight ซ้ำ) |
| 3.4-4.0 | H20 | 178 | 995.78 | 949.43 | ❌ ข้าม — leg เดิม S113 (weight ซ้ำ) |
| 3.4-4.0 | H15 | 150 | 990.42 | 952.62 | candidate รอบถัดไป |

หมายเหตุ: H10-11 (RD 1.3-2.0) เป็น subset ของ S96 (H10-13 x6.628) — precedent เดียว
กับ S111 (H11-12) ที่ re-slice รายชั่วโมงบน band เดิมได้

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin1.3_rd2_hfrom10_hbefore11
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `1.3 <= risk_distance <= 2.0`
- Time filter: `10 <= fill_hour < 11` BKK
- Raw trades: 3/3/7/11 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
  (best w 172 < grid cap 300 → ไม่ใช่ degenerate)
- Leg equity stats: lot_max 0.04, leg DD 0.60%, skipped 0

## New Champion

```text
S116 = S115 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0_H10_11x172.426
```

| Metric | S116 |
|---|---:|
| Avg $/day | 1005.7896 |
| Min $/day | 963.2122 |
| Min PF | 8.14293 |
| Max losing-day streak | 3 |
| Worst day | -999.90926 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10495 |

Per-window exact from `s116_s84_inv_rdmin13_rd20_h10_11_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 963.2122 | 8.22800 | 2 | -999.90825 | 3 |
| 120 | 1021.8215 | 9.22906 | 2 | -997.45850 | 3 |
| 150 | 1027.5552 | 8.63828 | 3 | -999.90926 | 7 |
| 180 | 1010.5695 | 8.14293 | 3 | -999.90886 | 11 |

## Weight Threshold

`s116_s84_inv_rdmin13_rd20_h10_11_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 172.426 | highest 0.001-step weight that passes `-999.91` |
| 172.427 | fails `-999.91` |

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
- `s116_s84_inv_rdmin13_rd20_h10_11_target28_probe.csv`
- `s116_s84_inv_rdmin13_rd20_h10_11_target28_fine.csv`
- `s116_s84_inv_rdmin13_rd20_h10_11_target28_ultrafine.csv`
- `s116_s84_inv_rdmin13_rd20_h10_11_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S116 uses `s115_s84_inv_rdmin20_rd27_h20_21_daily.csv` as the base, so it is
  compared against the current champion S115.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`; fill from `j+1` via `sim_s84_backtest.run_single`.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `10 <= fill_hour < 11` uses the simulated fill timestamp available at entry,
  not any post-entry outcome.
- No future candle, same-bar close fill, or result filter is used.

## ⚠️ คำเตือนสำคัญ (in-sample overfit risk)

Ladder S89→S116 ทั้งหมดคือการ re-weight trade stream ของ S84 generator เดียวกันด้วย
filter มิติต่างๆ (RD band × hour) และ weight ถูก optimize ชิดขอบ floor ในข้อมูล
in-sample เดียวกันทุกchั้น — ตัวเลข $1005/วัน **ไม่ใช่การคาดการณ์ out-of-sample**
ควรมองเป็น upper bound ของ framework นี้ ก่อน deploy จริงต้องทำ walk-forward /
out-of-sample validation เหมือนที่เคยพบใน S21-S58 ว่าตัวเลข in-sample สูงเกินจริงได้มาก

## Verdict

Found new champion and reached the $1000/day goal:

```text
S116 = S115 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0_H10_11x172.426
```

This improves avg $/day (980.07 → 1005.79) and min $/day (935.45 → 963.21) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S117 search using S116 as the new baseline — เป้าถัดไป: min window
≥ $1000 แล้วไล่ $1500 → $2000.
