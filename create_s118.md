# S118 Champion - Inverse S84 RD 3.4-4.0 H17-18 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

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

## Search Space รอบนี้

Batch sweep ทุก band × hour บน S117 base — Top candidates:

| Band | Hour | Best w | avg | min | หมายเหตุ |
|---|---|---:|---:|---:|---|
| 1.3-2.0 | H20 | 300 (cap) | 1077.42 | 1013.31 | ❌ ข้าม — S103 degenerate leg |
| 3.4-4.0 | H19 | 254 | 1041.40 | 989.16 | ❌ ข้าม — leg เดิม S114 |
| 3.4-4.0 | H20 | 178 | 1031.98 | 994.59 | ❌ ข้าม — leg เดิม S113 |
| **3.4-4.0** | **H17** | **148** | **1020.90** | **986.48** | ✅ ผู้ชนะ |
| 2.0-2.7 | H18 | 144 | 1017.90 | 1005.95 | candidate S119 (min ทะลุ $1000) |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin3.4_rd4_hfrom17_hbefore18
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `3.4 <= risk_distance <= 4.0`
- Time filter: `17 <= fill_hour < 18` BKK
- Raw trades: 3/6/9/10 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
- Leg equity stats: lot_max 0.01, leg DD 1.07%, skipped 0

## New Champion

```text
S118 = S117 + INV_S84_M15_OLDWICK_FOLLOW_RD3.4_4.0_H17_18x149.023
```

| Metric | S118 |
|---|---:|
| Avg $/day | 1020.9369 |
| Min $/day | 986.5169 |
| Min PF | 7.87677 |
| Max losing-day streak | 3 |
| Worst day | -999.90930 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10495 |

Per-window exact from `s118_s84_inv_rdmin34_rd40_h17_18_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 986.5169 | 8.10724 | 2 | -999.90825 | 3 |
| 120 | 1039.6772 | 8.58112 | 2 | -999.90834 | 6 |
| 150 | 1041.1536 | 8.53547 | 3 | -999.90926 | 9 |
| 180 | 1016.3999 | 7.87677 | 3 | -999.90930 | 10 |

## Weight Threshold

`s118_s84_inv_rdmin34_rd40_h17_18_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 149.023 | highest 0.001-step weight that passes `-999.91` |
| 149.024 | fails `-999.91` |

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
- `s118_s84_inv_rdmin34_rd40_h17_18_target28_probe.csv`
- `s118_s84_inv_rdmin34_rd40_h17_18_target28_fine.csv`
- `s118_s84_inv_rdmin34_rd40_h17_18_target28_ultrafine.csv`
- `s118_s84_inv_rdmin34_rd40_h17_18_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S118 uses `s117_s84_inv_rdmin34_rd40_h15_16_daily.csv` as the base, so it is
  compared against the current champion S117.
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
S118 = S117 + INV_S84_M15_OLDWICK_FOLLOW_RD3.4_4.0_H17_18x149.023
```

This improves avg $/day (1016.27 → 1020.94) and min $/day (980.61 → 986.52) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S119 search using S118 as the new baseline (2.0-2.7 H18 คือ candidate
แรก — จะดัน min window ทะลุ $1000).
