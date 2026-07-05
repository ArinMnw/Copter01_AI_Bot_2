# S112 Champion - Inverse S84 RD 3.4-4.0 H11-12 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S111 = S110 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0_H11_12x186.769
```

| Metric | S111 |
|---|---:|
| Avg $/day | 891.6791 |
| Min $/day | 865.6829 |
| Min PF | 7.25898 |
| Max losing-day streak | 3 |
| Worst day | -999.90926 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10495 |

## Search Space รอบนี้

Batch sweep ทุก band × hour บน S111 base — Top candidates (ข้าม 1.3-2.0 H20 = S103
degenerate leg เช่นเดิม):

| Band | Hour | Best w | avg | min | หมายเหตุ |
|---|---|---:|---:|---:|---|
| **3.4-4.0** | **H11** | **274** | **926.11** | **898.62** | ✅ ผู้ชนะ |
| 3.4-4.0 | H20 | 218 | 910.92 | 882.81 | candidate รอบถัดไป |
| 2.0-2.7 | H17 | 166 | 910.08 | 888.52 | candidate |
| 3.4-4.0 | H19 | 188 | 910.28 | 872.01 | candidate |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin3.4_rd4_hfrom11_hbefore12
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `3.4 <= risk_distance <= 4.0`
- Time filter: `11 <= fill_hour < 12` BKK
- Raw trades: 9/13/13/14 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
- Leg equity stats: lot_max 0.01, leg DD 0.66%, skipped 0

## New Champion

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

Per-window exact from `s112_s84_inv_rdmin34_rd40_h11_12_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 898.8040 | 8.00192 | 2 | -999.90825 | 9 |
| 120 | 949.0765 | 8.06034 | 2 | -997.45850 | 13 |
| 150 | 952.0509 | 7.89569 | 3 | -999.90926 | 13 |
| 180 | 905.2492 | 7.57399 | 3 | -999.90886 | 14 |

## Weight Threshold

`s112_s84_inv_rdmin34_rd40_h11_12_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 275.499 | highest 0.001-step weight that passes `-999.91` |
| 275.500 | fails `-999.91` |

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
- `s112_s84_inv_rdmin34_rd40_h11_12_target28_probe.csv`
- `s112_s84_inv_rdmin34_rd40_h11_12_target28_fine.csv`
- `s112_s84_inv_rdmin34_rd40_h11_12_target28_ultrafine.csv`
- `s112_s84_inv_rdmin34_rd40_h11_12_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S112 uses `s111_s84_inv_rdmin13_rd20_h11_12_daily.csv` as the base, so it is
  compared against the current champion S111.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`; fill from `j+1` via `sim_s84_backtest.run_single`.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `11 <= fill_hour < 12` uses the simulated fill timestamp available at entry,
  not any post-entry outcome.
- No future candle, same-bar close fill, or result filter is used.

## Verdict

Found new champion:

```text
S112 = S111 + INV_S84_M15_OLDWICK_FOLLOW_RD3.4_4.0_H11_12x275.499
```

This improves avg $/day (891.68 → 926.30) and min $/day (865.68 → 898.80) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S113 search using S112 as the new baseline.
