# S117 Champion - Inverse S84 RD 3.4-4.0 H15-16 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

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

## Search Space รอบนี้

Batch sweep ทุก band × hour บน S116 base — Top candidates:

| Band | Hour | Best w | avg | min | หมายเหตุ |
|---|---|---:|---:|---:|---|
| 1.3-2.0 | H20 | 300 (cap) | 1066.94 | 995.91 | ❌ ข้าม — S103 degenerate leg |
| 3.4-4.0 | H19 | 254 | 1030.92 | 971.76 | ❌ ข้าม — leg เดิม S114 |
| 3.4-4.0 | H20 | 178 | 1021.50 | 977.20 | ❌ ข้าม — leg เดิม S113 |
| **3.4-4.0** | **H15** | **150** | **1016.13** | **980.38** | ✅ ผู้ชนะ |
| 2.0-2.7 | H18 | 144 | 1007.42 | 988.56 | candidate รอบถัดไป (min สูง) |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin3.4_rd4_hfrom15_hbefore16
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `3.4 <= risk_distance <= 4.0`
- Time filter: `15 <= fill_hour < 16` BKK
- Raw trades: 7/8/11/14 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
- Leg equity stats: lot_max 0.01, leg DD 0.70%, skipped 0

## New Champion

```text
S117 = S116 + INV_S84_M15_OLDWICK_FOLLOW_RD3.4_4.0_H15_16x151.982
```

| Metric | S117 |
|---|---:|
| Avg $/day | 1016.2700 |
| Min $/day | 980.6057 |
| Min PF | 8.00871 |
| Max losing-day streak | 3 |
| Worst day | -999.90930 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10495 |

Per-window exact from `s117_s84_inv_rdmin34_rd40_h15_16_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 980.6057 | 8.06466 | 2 | -999.90825 | 7 |
| 120 | 1030.6365 | 8.76990 | 2 | -997.45850 | 8 |
| 150 | 1037.6367 | 8.63010 | 3 | -999.90926 | 11 |
| 180 | 1016.2012 | 8.00871 | 3 | -999.90930 | 14 |

## Weight Threshold

`s117_s84_inv_rdmin34_rd40_h15_16_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 151.982 | highest 0.001-step weight that passes `-999.91` |
| 151.983 | fails `-999.91` |

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
- `s117_s84_inv_rdmin34_rd40_h15_16_target28_probe.csv`
- `s117_s84_inv_rdmin34_rd40_h15_16_target28_fine.csv`
- `s117_s84_inv_rdmin34_rd40_h15_16_target28_ultrafine.csv`
- `s117_s84_inv_rdmin34_rd40_h15_16_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S117 uses `s116_s84_inv_rdmin13_rd20_h10_11_daily.csv` as the base, so it is
  compared against the current champion S116.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`; fill from `j+1` via `sim_s84_backtest.run_single`.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `15 <= fill_hour < 16` uses the simulated fill timestamp available at entry,
  not any post-entry outcome.
- No future candle, same-bar close fill, or result filter is used.

## Verdict

Found new champion:

```text
S117 = S116 + INV_S84_M15_OLDWICK_FOLLOW_RD3.4_4.0_H15_16x151.982
```

This improves avg $/day (1005.79 → 1016.27) and min $/day (963.21 → 980.61) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S118 search using S117 as the new baseline (2.0-2.7 H18 คือ candidate
ถัดไป — min สูง).
