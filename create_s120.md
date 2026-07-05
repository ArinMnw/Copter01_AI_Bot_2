# S120 Champion - Inverse S84 RD 2.0-2.7 H12-13 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

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

## Search Space รอบนี้

Batch sweep ทุก band × hour บน S119 base — Top candidates (ข้าม repeats: 1.3-2.0
H20=S103, 3.4-4.0 H19=S114, 3.4-4.0 H20=S113, 2.7-3.4 H16=S108, 2.0-2.7 H14=S110):

| Band | Hour | Best w | avg | min | หมายเหตุ |
|---|---|---:|---:|---:|---|
| **2.0-2.7** | **H12** | **108** | **1043.92** | **1026.03** | ✅ ผู้ชนะ |
| 3.4-4.0 | H8 | 148 | 1034.09 | 1017.22 | candidate รอบถัดไป |
| 2.7-3.4 | H20 | 30 | 1027.51 | 1013.49 | candidate |
| 2.7-3.4 | H9 | 74 | 1027.01 | 1010.97 | candidate |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin2_rd2.7_hfrom12_hbefore13
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `2.0 <= risk_distance <= 2.7`
- Time filter: `12 <= fill_hour < 13` BKK
- Raw trades: 15/16/21/24 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
- Leg equity stats: lot_max 0.03, leg DD 1.11%, skipped 0

## New Champion

```text
S120 = S119 + INV_S84_M15_OLDWICK_FOLLOW_RD2.0_2.7_H12_13x108.636
```

| Metric | S120 |
|---|---:|
| Avg $/day | 1044.0487 |
| Min $/day | 1026.1208 |
| Min PF | 8.28525 |
| Max losing-day streak | 3 |
| Worst day | -999.90930 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10505 |

Per-window exact from `s120_s84_inv_rdmin20_rd27_h12_13_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1040.9920 | 10.57981 | 2 | -999.90825 | 15 |
| 120 | 1057.3909 | 9.68767 | 2 | -999.90834 | 16 |
| 150 | 1051.6913 | 9.13186 | 3 | -999.90687 | 21 |
| 180 | 1026.1208 | 8.28525 | 3 | -999.90930 | 24 |

## Weight Threshold

`s120_s84_inv_rdmin20_rd27_h12_13_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 108.636 | highest 0.001-step weight that passes `-999.91` |
| 108.637 | fails `-999.91` |

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
- `s120_s84_inv_rdmin20_rd27_h12_13_target28_probe.csv`
- `s120_s84_inv_rdmin20_rd27_h12_13_target28_fine.csv`
- `s120_s84_inv_rdmin20_rd27_h12_13_target28_ultrafine.csv`
- `s120_s84_inv_rdmin20_rd27_h12_13_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S120 uses `s119_s84_inv_rdmin20_rd27_h18_19_daily.csv` as the base, so it is
  compared against the current champion S119.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`; fill from `j+1` via `sim_s84_backtest.run_single`.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `12 <= fill_hour < 13` uses the simulated fill timestamp available at entry,
  not any post-entry outcome.
- No future candle, same-bar close fill, or result filter is used.

## Verdict

Found new champion:

```text
S120 = S119 + INV_S84_M15_OLDWICK_FOLLOW_RD2.0_2.7_H12_13x108.636
```

This improves avg $/day (1022.58 → 1044.05) and min $/day (1010.04 → 1026.12) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S121 search using S120 as the new baseline — เป้าถัดไป $1500/วัน
(candidates: 3.4-4.0 H8, 2.7-3.4 H20, 2.7-3.4 H9).
