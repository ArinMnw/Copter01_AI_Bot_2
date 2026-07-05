# S121 Champion - Inverse S84 RD 2.7-3.4 H20-21 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

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

## Search Space รอบนี้

Batch sweep ทุก band × hour บน S120 base — Top candidates (ข้าม repeats: 1.3-2.0
H20=S103, 3.4-4.0 H19=S114, 3.4-4.0 H20=S113, 2.0-2.7 H14=S110, 2.7-3.4 H8=S107):

| Band | Hour | Best w | avg | min | หมายเหตุ |
|---|---|---:|---:|---:|---|
| **2.7-3.4** | **H20** | **30** | **1048.98** | **1029.57** | ✅ ผู้ชนะ |
| 2.7-3.4 | H9 | 74 | 1048.48 | 1038.29 | candidate รอบถัดไป |
| 3.4-4.0 | H10 | 88 | 1044.90 | 1027.65 | candidate |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin2.7_rd3.4_hfrom20_hbefore21
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `2.7 <= risk_distance <= 3.4`
- Time filter: `20 <= fill_hour < 21` BKK
- Raw trades: 10/10/14/16 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
- Leg equity stats: lot_max 0.02, leg DD 1.10%, skipped 0

## New Champion

```text
S121 = S120 + INV_S84_M15_OLDWICK_FOLLOW_RD2.7_3.4_H20_21x30.194
```

| Metric | S121 |
|---|---:|
| Avg $/day | 1049.0123 |
| Min $/day | 1029.5931 |
| Min PF | 8.40086 |
| Max losing-day streak | 3 |
| Worst day | -999.90930 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10505 |

Per-window exact from `s121_s84_inv_rdmin27_rd34_h20_21_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1047.9836 | 10.63701 | 2 | -999.90825 | 10 |
| 120 | 1062.6346 | 9.72642 | 2 | -999.90834 | 10 |
| 150 | 1055.8379 | 9.29589 | 3 | -999.90687 | 14 |
| 180 | 1029.5931 | 8.40086 | 3 | -999.90930 | 16 |

## Weight Threshold

`s121_s84_inv_rdmin27_rd34_h20_21_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 30.194 | highest 0.001-step weight that passes `-999.91` |
| 30.195 | fails `-999.91` |

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
- `s121_s84_inv_rdmin27_rd34_h20_21_target28_probe.csv`
- `s121_s84_inv_rdmin27_rd34_h20_21_target28_fine.csv`
- `s121_s84_inv_rdmin27_rd34_h20_21_target28_ultrafine.csv`
- `s121_s84_inv_rdmin27_rd34_h20_21_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S121 uses `s120_s84_inv_rdmin20_rd27_h12_13_daily.csv` as the base, so it is
  compared against the current champion S120.
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
S121 = S120 + INV_S84_M15_OLDWICK_FOLLOW_RD2.7_3.4_H20_21x30.194
```

This improves avg $/day (1044.05 → 1049.01) and min $/day (1026.12 → 1029.59) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S122 search using S121 as the new baseline (2.7-3.4 H9 / 3.4-4.0 H10
คือ candidates ถัดไป) — เป้าถัดไป $1500/วัน.
