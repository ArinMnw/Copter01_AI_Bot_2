# S114 Champion - Inverse S84 RD 3.4-4.0 H19-20 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

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

## Search Space รอบนี้

Batch sweep ทุก band × hour บน S113 base — Top candidates (ข้าม 1.3-2.0 H20 = S103
degenerate leg เช่นเดิม):

| Band | Hour | Best w | avg | min | หมายเหตุ |
|---|---|---:|---:|---:|---|
| **3.4-4.0** | **H19** | **188** | **964.25** | **922.36** | ✅ ผู้ชนะ |
| 2.0-2.7 | H20 | 206 | 961.32 | 929.04 | candidate รอบถัดไป |
| 3.4-4.0 | H15 | 98 | 952.41 | 927.25 | candidate |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin3.4_rd4_hfrom19_hbefore20
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `3.4 <= risk_distance <= 4.0`
- Time filter: `19 <= fill_hour < 20` BKK
- Raw trades: 7/9/12/18 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
- Leg equity stats: lot_max 0.02, leg DD 0.70%, skipped 0

## New Champion

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

Per-window exact from `s114_s84_inv_rdmin34_rd40_h19_20_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 922.3931 | 8.01192 | 2 | -999.90825 | 7 |
| 120 | 984.2412 | 8.65234 | 2 | -997.45850 | 9 |
| 150 | 989.0904 | 8.21713 | 3 | -999.90926 | 12 |
| 180 | 961.6272 | 7.91343 | 3 | -999.90886 | 18 |

## Weight Threshold

`s114_s84_inv_rdmin34_rd40_h19_20_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 188.882 | highest 0.001-step weight that passes `-999.91` |
| 188.883 | fails `-999.91` |

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
- `s114_s84_inv_rdmin34_rd40_h19_20_target28_probe.csv`
- `s114_s84_inv_rdmin34_rd40_h19_20_target28_fine.csv`
- `s114_s84_inv_rdmin34_rd40_h19_20_target28_ultrafine.csv`
- `s114_s84_inv_rdmin34_rd40_h19_20_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S114 uses `s113_s84_inv_rdmin34_rd40_h20_21_daily.csv` as the base, so it is
  compared against the current champion S113.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`; fill from `j+1` via `sim_s84_backtest.run_single`.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `19 <= fill_hour < 20` uses the simulated fill timestamp available at entry,
  not any post-entry outcome.
- No future candle, same-bar close fill, or result filter is used.

## Verdict

Found new champion:

```text
S114 = S113 + INV_S84_M15_OLDWICK_FOLLOW_RD3.4_4.0_H19_20x188.882
```

This improves avg $/day (945.65 → 964.34) and min $/day (916.03 → 922.39) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S115 search using S114 as the new baseline — เหลือ ~$36/วัน ถึงเป้า
$1000/วัน.
