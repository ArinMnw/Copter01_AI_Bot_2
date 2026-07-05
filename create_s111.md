# S111 Champion - Inverse S84 RD 1.3-2.0 H11-12 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

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

## Search Space รอบนี้

Batch sweep ทุก band × hour บน S110 base — Top candidates (ข้าม 1.3-2.0 H20 ที่เป็น
leg เดียวกับ S103 ซึ่ง stress-capped ไว้แล้ว):

| Band | Hour | Best w | avg | min | หมายเหตุ |
|---|---|---:|---:|---:|---|
| **1.3-2.0** | **H11** | **186** | **891.52** | **865.51** | ✅ ผู้ชนะ |
| 3.4-4.0 | H11 | 274 | 888.65 | 857.16 | candidate รอบถัดไป |
| 3.4-4.0 | H20 | 218 | 873.46 | 841.35 | candidate |
| 2.0-2.7 | H17 | 166 | 872.62 | 847.05 | candidate |

หมายเหตุ: H11-12 (RD 1.3-2.0) เคย fail ตอน probe บน base เก่า (S96 คุม H10-13 อยู่แล้ว
ด้วย weight รวม) แต่บน base ปัจจุบันที่ 90d window แข็งแรงขึ้น candidate นี้ผ่าน beats
ได้จริง — เป็น slice ใหม่ที่ไม่ซ้ำกับ leg เดิม (S96 เป็น H10-13 x6.628 คนละ granularity)

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin1.3_rd2_hfrom11_hbefore12
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `1.3 <= risk_distance <= 2.0`
- Time filter: `11 <= fill_hour < 12` BKK
- Raw trades: 7/8/9/10 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
  (best w 186 < grid cap 300 → ไม่ใช่ degenerate)
- Leg equity stats: lot_max 0.03, leg DD 0.59%, skipped 0

## New Champion

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

Per-window exact from `s111_s84_inv_rdmin13_rd20_h11_12_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 865.6829 | 7.54413 | 2 | -999.90582 | 7 |
| 120 | 908.4174 | 7.75256 | 2 | -981.88805 | 8 |
| 150 | 919.5236 | 7.65703 | 3 | -999.90926 | 9 |
| 180 | 873.0924 | 7.25898 | 3 | -999.90886 | 10 |

## Weight Threshold

`s111_s84_inv_rdmin13_rd20_h11_12_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 186.769 | highest 0.001-step weight that passes `-999.91` |
| 186.770 | fails `-999.91` |

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
- `s111_s84_inv_rdmin13_rd20_h11_12_target28_probe.csv`
- `s111_s84_inv_rdmin13_rd20_h11_12_target28_fine.csv`
- `s111_s84_inv_rdmin13_rd20_h11_12_target28_ultrafine.csv`
- `s111_s84_inv_rdmin13_rd20_h11_12_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S111 uses `s110_s84_inv_rdmin20_rd27_h14_15_daily.csv` as the base, so it is
  compared against the current champion S110.
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
S111 = S110 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0_H11_12x186.769
```

This improves avg $/day (854.22 → 891.68) and min $/day (824.22 → 865.68) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S112 search using S111 as the new baseline.
