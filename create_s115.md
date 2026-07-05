# S115 Champion - Inverse S84 RD 2.0-2.7 H20-21 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S114 = S113 + INV_S84_M15_OLDWICK_FOLLOW_RD3.4_4.0_H19_20x188.882
```

| Metric | S114 |
|---|---:|
| Avg $/day | 964.3380 |
| Min $/day | 922.3931 |
| Min PF | 7.91343 |
| Max losing-day streak | 3 |
| Worst day | -999.90926 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10495 |

## Search Space รอบนี้

Batch sweep ทุก band × hour บน S114 base — Top candidates:

| Band | Hour | Best w | avg | min | หมายเหตุ |
|---|---|---:|---:|---:|---|
| 1.3-2.0 | H20 | 300 (cap) | 1025.48 | 955.09 | ❌ ข้าม — S103 degenerate leg |
| 3.4-4.0 | H20 | 178 | 980.05 | 936.38 | ❌ ข้าม — leg เดิมของ S113 (จะเป็นการเพิ่ม weight ซ้ำ leg เดียวกัน) |
| **2.0-2.7** | **H20** | **206** | **980.00** | **935.39** | ✅ ผู้ชนะ — leg ใหม่ คะแนนแทบเท่าอันดับสอง |
| 3.4-4.0 | H15 | 130 | 973.30 | 937.27 | candidate รอบถัดไป |
| 3.4-4.0 | H17 | 288 | 973.36 | 933.82 | candidate |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin2_rd2.7_hfrom20_hbefore21
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `2.0 <= risk_distance <= 2.7`
- Time filter: `20 <= fill_hour < 21` BKK
- Raw trades: 8/9/11/15 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
- Leg equity stats: lot_max 0.02, leg DD 0.62%, skipped 0

## New Champion

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

Per-window exact from `s115_s84_inv_rdmin20_rd27_h20_21_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 935.4516 | 8.01968 | 2 | -999.90825 | 8 |
| 120 | 1001.0011 | 9.06139 | 2 | -997.45850 | 9 |
| 150 | 1002.1396 | 8.83773 | 3 | -999.90926 | 11 |
| 180 | 981.6977 | 8.18790 | 3 | -999.90886 | 15 |

หมายเหตุ: window 120d และ 150d ทะลุ $1000/วันแล้ว

## Weight Threshold

`s115_s84_inv_rdmin20_rd27_h20_21_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 206.912 | highest 0.001-step weight that passes `-999.91` |
| 206.913 | fails `-999.91` |

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
- `s115_s84_inv_rdmin20_rd27_h20_21_target28_probe.csv`
- `s115_s84_inv_rdmin20_rd27_h20_21_target28_fine.csv`
- `s115_s84_inv_rdmin20_rd27_h20_21_target28_ultrafine.csv`
- `s115_s84_inv_rdmin20_rd27_h20_21_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S115 uses `s114_s84_inv_rdmin34_rd40_h19_20_daily.csv` as the base, so it is
  compared against the current champion S114.
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
S115 = S114 + INV_S84_M15_OLDWICK_FOLLOW_RD2.0_2.7_H20_21x206.912
```

This improves avg $/day (964.34 → 980.07) and min $/day (922.39 → 935.45) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S116 search using S115 as the new baseline — เหลือ ~$20/วัน ถึงเป้า
avg $1000/วัน.
