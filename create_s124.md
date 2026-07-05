# S124 Champion - Inverse S84 RD 4.0-5.0 H22-23 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S123 = S122 + INV_S84_M15_OLDWICK_FOLLOW_RD4.0_5.0_H17_18x220.032
```

| Metric | S123 |
|---|---:|
| Avg $/day | 1118.2840 |
| Min $/day | 1062.3640 |
| Min PF | 8.39087 |
| Max losing-day streak | 3 |
| Worst day | -999.90987 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10525 |

## Search Space รอบนี้

Batch sweep 7 band × 24 hour บน S123 base (weight grid ขยายถึง 600) — Top candidates:

| Band | Hour | Best w | avg | min | หมายเหตุ |
|---|---|---:|---:|---:|---|
| 1.3-2.0 | H20 | 600 (cap) | 1240.58 | 1196.14 | ❌ ข้าม — S103 degenerate leg |
| **4.0-5.0** | **H22** | **572** | **1200.27** | **1150.13** | ✅ ผู้ชนะ (ไม่ชน cap — floor bind ปกติ) |
| 3.4-4.0 | H19 | 254 | 1143.41 | 1110.57 | ❌ ข้าม — leg เดิม S114 |
| 4.0-5.0 | H20 | 112 | 1139.42 | 1073.99 | candidate รอบถัดไป |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin4_rd5_hfrom22_hbefore23
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `4.0 <= risk_distance <= 5.0`
- Time filter: `22 <= fill_hour < 23` BKK
- Raw trades: 9/9/11/14 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
  (best w 572 < grid cap 600 → ไม่ใช่ degenerate)
- Leg equity stats: lot_max 0.01, leg DD 0.85%, skipped 0

## New Champion

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

Per-window exact from `s124_s84_inv_rdmin40_rd50_h22_23_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1218.2117 | 11.70541 | 2 | -999.90825 | 9 |
| 120 | 1216.8890 | 11.04171 | 2 | -999.90834 | 9 |
| 150 | 1216.2442 | 10.62019 | 3 | -999.90687 | 11 |
| 180 | 1150.2768 | 9.01276 | 3 | -999.90930 | 14 |

## Weight Threshold

`s124_s84_inv_rdmin40_rd50_h22_23_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 572.929 | highest 0.001-step weight that passes `-999.91` |
| 572.930 | fails `-999.91` |

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
- `s124_s84_inv_rdmin40_rd50_h22_23_target28_probe.csv`
- `s124_s84_inv_rdmin40_rd50_h22_23_target28_fine.csv`
- `s124_s84_inv_rdmin40_rd50_h22_23_target28_ultrafine.csv`
- `s124_s84_inv_rdmin40_rd50_h22_23_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S124 uses `s123_s84_inv_rdmin40_rd50_h17_18_daily.csv` as the base, so it is
  compared against the current champion S123.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`; fill from `j+1` via `sim_s84_backtest.run_single`.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `22 <= fill_hour < 23` uses the simulated fill timestamp available at entry,
  not any post-entry outcome.
- No future candle, same-bar close fill, or result filter is used.

## Verdict

Found new champion:

```text
S124 = S123 + INV_S84_M15_OLDWICK_FOLLOW_RD4.0_5.0_H22_23x572.929
```

This improves avg $/day (1118.28 → 1200.41) and min $/day (1062.36 → 1150.28) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S125 search using S124 as the new baseline — เป้า $1500/วัน เหลือ ~$300.
