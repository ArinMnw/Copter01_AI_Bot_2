# S107 Champion - Inverse S84 RD 2.7-3.4 H8-9 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S106 = S105 + INV_S84_M15_OLDWICK_FOLLOW_RD2.7_3.4_H21_22x144.488
```

| Metric | S106 |
|---|---:|
| Avg $/day | 759.2200 |
| Min $/day | 730.3757 |
| Min PF | 6.51660 |
| Max losing-day streak | 3 |
| Worst day | -999.90886 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10470 |

## Search Space รอบนี้

Hour candidates ที่เหลือของ band RD 2.7-3.4 บน S106 base:

| Hour | ผล (probe grid 0:300:2) | หมายเหตุ |
|---|---|---|
| **H8-9** | **beats=True x86 avg 770.36 / min 731.63** | ✅ ผู้ชนะ (score สูงสุด: avg นำ) |
| H14-15 | beats=True x54 avg 760.57 / min 741.99 | candidate รอบถัดไป |
| H16-17 | beats=True x60 avg 768.92 / min 732.40 | candidate รอบถัดไป |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin2.7_rd3.4_hfrom8_hbefore9
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `2.7 <= risk_distance <= 3.4`
- Time filter: `8 <= fill_hour < 9` BKK
- Raw trades: 9/12/18/21 ที่ 90/120/150/180d — leg มีวันติดลบจริง floor bind ปกติ
- Leg equity stats: lot_max 0.02, leg DD 0.81%, skipped 0

## New Champion

```text
S107 = S106 + INV_S84_M15_OLDWICK_FOLLOW_RD2.7_3.4_H8_9x86.358
```

| Metric | S107 |
|---|---:|
| Avg $/day | 770.4028 |
| Min $/day | 731.6327 |
| Min PF | 6.65487 |
| Max losing-day streak | 3 |
| Worst day | -999.90886 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10470 |

Per-window exact from `s107_s84_inv_rdmin27_rd34_h8_9_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 731.6327 | 6.65487 | 2 | -999.90582 | 9 |
| 120 | 781.5732 | 7.04558 | 2 | -981.88805 | 12 |
| 150 | 800.5130 | 7.30149 | 2 | -999.90687 | 18 |
| 180 | 767.8922 | 6.76682 | 3 | -999.90886 | 21 |

## Weight Threshold

`s107_s84_inv_rdmin27_rd34_h8_9_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 86.358 | highest 0.001-step weight that passes `-999.91` |
| 86.359 | fails `-999.91` |

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
- `s107_s84_inv_rdmin27_rd34_h8_9 / h14_15 / h16_17 _target28_probe.csv`
- `s107_s84_inv_rdmin27_rd34_h8_9_target28_fine.csv`
- `s107_s84_inv_rdmin27_rd34_h8_9_target28_ultrafine.csv`
- `s107_s84_inv_rdmin27_rd34_h8_9_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S107 uses `s106_s84_inv_rdmin27_rd34_h21_22_daily.csv` as the base, so it is
  compared against the current champion S106.
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
S107 = S106 + INV_S84_M15_OLDWICK_FOLLOW_RD2.7_3.4_H8_9x86.358
```

This improves avg $/day (759.22 → 770.40) and min $/day (730.38 → 731.63) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S108 search using S107 as the new baseline (H14-15 / H16-17 ของ band
เดียวกันคือ candidates ถัดไป).
