# S127 Champion - Inverse S84 RD 3.4-4.0 H8-9 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S126 = S125 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0_H13_14x27.964
```

| Metric | S126 |
|---|---:|
| Avg $/day | 1227.0836 |
| Min $/day | 1168.3346 |
| Min PF | 9.12236 |
| Max losing-day streak | 3 |
| Worst day | -999.90930 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10525 |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin3.4_rd4_hfrom8_hbefore9
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `3.4 <= risk_distance <= 4.0`
- Time filter: `8 <= fill_hour < 9` BKK
- ไม่ซ้ำกับ S107 (2.7-3.4 H8) และ S98 (1.3-2.0 H8) — คนละ RD band
- Raw trades: 13/14/19/20 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
- Leg equity stats: lot_max 0.02, leg DD 1.32%, skipped 0

## New Champion

```text
S127 = S126 + INV_S84_M15_OLDWICK_FOLLOW_RD3.4_4.0_H8_9x46.180
```

| Metric | S127 |
|---|---:|
| Avg $/day | 1230.6751 |
| Min $/day | 1173.4836 |
| Min PF | 9.25519 |
| Max losing-day streak | 3 |
| Worst day | -999.90930 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10525 |

Per-window exact from `s127_s84_inv_rdmin34_rd40_h8_9_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1254.9284 | 12.19346 | 2 | -999.90825 | 13 |
| 120 | 1248.3647 | 11.49587 | 2 | -999.90834 | 14 |
| 150 | 1245.9239 | 10.76282 | 3 | -999.90896 | 19 |
| 180 | 1173.4836 | 9.25519 | 3 | -999.90930 | 20 |

## Weight Threshold

`s127_s84_inv_rdmin34_rd40_h8_9_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 46.180 | highest 0.001-step weight that passes `-999.91` |
| 46.181 | fails `-999.91` |

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
- `s127_s84_inv_rdmin34_rd40_h8_9_target28_probe.csv`
- `s127_s84_inv_rdmin34_rd40_h8_9_target28_fine.csv`
- `s127_s84_inv_rdmin34_rd40_h8_9_target28_ultrafine.csv`
- `s127_s84_inv_rdmin34_rd40_h8_9_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S127 uses `s126_s84_inv_rdmin13_rd20_h13_14_daily.csv` as the base, so it is
  compared against the current champion S126.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`; fill from `j+1` via `sim_s84_backtest.run_single`.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `8 <= fill_hour < 9` uses the simulated fill timestamp available at entry,
  not any post-entry outcome.
- No future candle, same-bar close fill, or result filter is used.

## Verdict

Found new champion:

```text
S127 = S126 + INV_S84_M15_OLDWICK_FOLLOW_RD3.4_4.0_H8_9x46.180
```

This improves avg $/day (1227.08 → 1230.68) and min $/day (1168.33 → 1173.48) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S128 search using S127 as the new baseline — เป้า $1500/วัน.
