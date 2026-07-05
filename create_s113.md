# S113 Champion - Inverse S84 RD 3.4-4.0 H20-21 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S112 = S111 + INV_S84_M15_OLDWICK_FOLLOW_RD3.4_4.0_H11_12x275.499
```

| Metric | S112 |
|---|---:|
| Avg $/day | 926.2952 |
| Min $/day | 898.8040 |
| Min PF | 7.57399 |
| Max losing-day streak | 3 |
| Worst day | -999.90926 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10495 |

## Search Space รอบนี้

Batch sweep ทุก band × hour บน S112 base — Top candidates (ข้าม 1.3-2.0 H20 = S103
degenerate leg เช่นเดิม):

| Band | Hour | Best w | avg | min | หมายเหตุ |
|---|---|---:|---:|---:|---|
| **3.4-4.0** | **H20** | **218** | **945.53** | **915.93** | ✅ ผู้ชนะ |
| 3.4-4.0 | H19 | 188 | 944.90 | 905.13 | candidate รอบถัดไป |
| 2.0-2.7 | H20 | 206 | 941.96 | 911.80 | candidate |
| 3.4-4.0 | H15 | 98 | 933.05 | 908.88 | candidate |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin3.4_rd4_hfrom20_hbefore21
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `3.4 <= risk_distance <= 4.0`
- Time filter: `20 <= fill_hour < 21` BKK
- Raw trades: 8/9/10/15 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
- Leg equity stats: lot_max 0.01, leg DD 0.70%, skipped 0

## New Champion

```text
S113 = S112 + INV_S84_M15_OLDWICK_FOLLOW_RD3.4_4.0_H20_21x219.337
```

| Metric | S113 |
|---|---:|
| Avg $/day | 945.6507 |
| Min $/day | 916.0341 |
| Min PF | 7.53003 |
| Max losing-day streak | 3 |
| Worst day | -999.90983 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10495 |

Per-window exact from `s113_s84_inv_rdmin34_rd40_h20_21_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 916.0341 | 8.04428 | 2 | -999.90825 | 8 |
| 120 | 968.4696 | 8.27337 | 2 | -997.45850 | 9 |
| 150 | 972.3176 | 8.09760 | 3 | -999.90926 | 10 |
| 180 | 925.7816 | 7.53003 | 3 | -999.90983 | 15 |

## Weight Threshold

`s113_s84_inv_rdmin34_rd40_h20_21_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 219.337 | highest 0.001-step weight that passes `-999.91` |
| 219.338 | fails `-999.91` |

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
- `s113_s84_inv_rdmin34_rd40_h20_21_target28_probe.csv`
- `s113_s84_inv_rdmin34_rd40_h20_21_target28_fine.csv`
- `s113_s84_inv_rdmin34_rd40_h20_21_target28_ultrafine.csv`
- `s113_s84_inv_rdmin34_rd40_h20_21_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S113 uses `s112_s84_inv_rdmin34_rd40_h11_12_daily.csv` as the base, so it is
  compared against the current champion S112.
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
S113 = S112 + INV_S84_M15_OLDWICK_FOLLOW_RD3.4_4.0_H20_21x219.337
```

This improves avg $/day (926.30 → 945.65) and min $/day (898.80 → 916.03) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S114 search using S113 as the new baseline.
