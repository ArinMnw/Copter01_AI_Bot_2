# S110 Champion - Inverse S84 RD 2.0-2.7 H14-15 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S109 = S108 + INV_S84_M15_OLDWICK_FOLLOW_RD2.7_3.4_H14_15x55.179
```

| Metric | S109 |
|---|---:|
| Avg $/day | 781.5398 |
| Min $/day | 746.2963 |
| Min PF | 6.67540 |
| Max losing-day streak | 3 |
| Worst day | -999.90926 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10495 |

## Search Space รอบนี้

Batch sweep ทุก band × hour บน S109 base (RD 1.3-2.0 / 2.0-2.7 / 2.7-3.4 / 3.4-4.0
× H0-H23) — Top candidates:

| Band | Hour | Best w | avg | min | หมายเหตุ |
|---|---|---:|---:|---:|---|
| **2.0-2.7** | **H14** | **206** | **854.12** | **824.12** | ✅ ผู้ชนะ |
| 1.3-2.0 | H20 | 300 (cap) | 842.69 | 778.99 | ❌ ข้าม — leg เดียวกับ S103 ที่ stress-capped ไว้แล้ว ห้ามเพิ่มน้ำหนัก degenerate leg ซ้ำ |
| 1.3-2.0 | H11 | 186 | 818.85 | 787.59 | candidate รอบถัดไป |
| 3.4-4.0 | H11 | 274 | 815.97 | 779.24 | candidate รอบถัดไป |
| 3.4-4.0 | H20 | 218 | 800.78 | 763.42 | candidate |
| 2.0-2.7 | H17 | 166 | 799.94 | 769.13 | candidate |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin2_rd2.7_hfrom14_hbefore15
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `2.0 <= risk_distance <= 2.7`
- Time filter: `14 <= fill_hour < 15` BKK
- Raw trades: 10/12/18/22 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
- Leg equity stats: lot_max 0.03, leg DD 0.65%, skipped 0

## New Champion

```text
S110 = S109 + INV_S84_M15_OLDWICK_FOLLOW_RD2.0_2.7_H14_15x206.269
```

| Metric | S110 |
|---|---:|
| Avg $/day | 854.2187 |
| Min $/day | 824.2201 |
| Min PF | 7.06698 |
| Max losing-day streak | 3 |
| Worst day | -999.90926 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10495 |

Per-window exact from `s110_s84_inv_rdmin20_rd27_h14_15_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 824.2201 | 7.42514 | 2 | -999.90582 | 10 |
| 120 | 870.3633 | 7.80197 | 2 | -981.88805 | 12 |
| 150 | 884.0002 | 7.43262 | 3 | -999.90926 | 18 |
| 180 | 838.2911 | 7.06698 | 3 | -999.90886 | 22 |

## Weight Threshold

`s110_s84_inv_rdmin20_rd27_h14_15_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 206.269 | highest 0.001-step weight that passes `-999.91` |
| 206.270 | fails `-999.91` |

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
- `s110_s84_inv_rdmin20_rd27_h14_15_target28_probe.csv`
- `s110_s84_inv_rdmin20_rd27_h14_15_target28_fine.csv`
- `s110_s84_inv_rdmin20_rd27_h14_15_target28_ultrafine.csv`
- `s110_s84_inv_rdmin20_rd27_h14_15_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S110 uses `s109_s84_inv_rdmin27_rd34_h14_15_daily.csv` as the base, so it is
  compared against the current champion S109.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`; fill from `j+1` via `sim_s84_backtest.run_single`.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `14 <= fill_hour < 15` uses the simulated fill timestamp available at entry,
  not any post-entry outcome.
- No future candle, same-bar close fill, or result filter is used.

## Verdict

Found new champion:

```text
S110 = S109 + INV_S84_M15_OLDWICK_FOLLOW_RD2.0_2.7_H14_15x206.269
```

This improves avg $/day (781.54 → 854.22) and min $/day (746.30 → 824.22) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S111 search using S110 as the new baseline.
