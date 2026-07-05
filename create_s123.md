# S123 Champion - Inverse S84 RD 4.0-5.0 H17-18 Overlay (เปิด band ใหม่)

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S122 = S121 + INV_S84_M15_OLDWICK_FOLLOW_RD2.7_3.4_H9_10x74.771
```

| Metric | S122 |
|---|---:|
| Avg $/day | 1053.4931 |
| Min $/day | 1041.8888 |
| Min PF | 8.45319 |
| Max losing-day streak | 3 |
| Worst day | -999.90930 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10515 |

## Search Space รอบนี้

ขยาย sweep เพิ่ม band ใหม่ RD 0.8-1.3 / **4.0-5.0** / 5.0-7.0 (จากเดิม 4 band) —
Top candidates บน S122 base:

| Band | Hour | Best w | avg | min | หมายเหตุ |
|---|---|---:|---:|---:|---|
| **4.0-5.0** | **H17** | **220** | **1118.27** | **1062.36** | ✅ ผู้ชนะ (band ใหม่) |
| 1.3-2.0 | H20 | 300 (cap) | 1114.64 | 1079.64 | ❌ ข้าม — S103 degenerate leg |
| 4.0-5.0 | H22 | 300 (cap) | 1096.49 | 1087.92 | candidate (ต้องเช็ค degenerate ก่อน) |
| 4.0-5.0 | H20 | 112 | 1074.63 | 1053.52 | candidate |
| 4.0-5.0 | H11 | 144 | 1066.68 | 1059.49 | candidate |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin4_rd5_hfrom17_hbefore18
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `4.0 <= risk_distance <= 5.0`
- Time filter: `17 <= fill_hour < 18` BKK
- Raw trades: 12/16/19/22 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
- Leg equity stats: lot_max 0.01, leg DD 1.31%, skipped 10

## New Champion

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

Per-window exact from `s123_s84_inv_rdmin40_rd50_h17_18_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1130.7445 | 11.28889 | 2 | -999.90825 | 12 |
| 120 | 1151.2887 | 10.11366 | 2 | -999.90834 | 16 |
| 150 | 1128.7389 | 9.60360 | 3 | -999.90987 | 19 |
| 180 | 1062.3640 | 8.39087 | 3 | -999.90930 | 22 |

## Weight Threshold

`s123_s84_inv_rdmin40_rd50_h17_18_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 220.032 | highest 0.001-step weight that passes `-999.91` |
| 220.033 | fails `-999.91` |

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
- `s123_s84_inv_rdmin40_rd50_h17_18_target28_probe.csv`
- `s123_s84_inv_rdmin40_rd50_h17_18_target28_fine.csv`
- `s123_s84_inv_rdmin40_rd50_h17_18_target28_ultrafine.csv`
- `s123_s84_inv_rdmin40_rd50_h17_18_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S123 uses `s122_s84_inv_rdmin27_rd34_h9_10_daily.csv` as the base, so it is
  compared against the current champion S122.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`; fill from `j+1` via `sim_s84_backtest.run_single`.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `17 <= fill_hour < 18` uses the simulated fill timestamp available at entry,
  not any post-entry outcome.
- No future candle, same-bar close fill, or result filter is used.

## Verdict

Found new champion:

```text
S123 = S122 + INV_S84_M15_OLDWICK_FOLLOW_RD4.0_5.0_H17_18x220.032
```

This improves avg $/day (1053.49 → 1118.28) and min $/day (1041.89 → 1062.36) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S124 search using S123 as the new baseline — band 4.0-5.0 ยังมี
candidates อีกหลายช่อง (H22 ต้องเช็ค degenerate ก่อนใช้ stress rule).
