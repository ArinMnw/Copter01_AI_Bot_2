# S131 Champion - Inverse S84 RD 2.0-2.7 H13-14 Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

> ⚠️ **อ่าน `create_ambfix_audit.md` ก่อน**: audit วันเดียวกันพิสูจน์ว่ากำไรส่วนเกิน
> ของ INV_S84 ladder เหนือ S88 base เป็น artifact ของ intrabar SL-first resolution
> (ภายใต้ M1-replay resolution ladder หลุด no-blow ตั้งแต่ S89) — S131 นี้ทำต่อ
> **ตาม convention เดิมในฐานะ framework benchmark เท่านั้น** ตามคำสั่งผู้ใช้
> ห้ามตีความ $/day เป็นความคาดหวังจริง

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S130 = S129 + INV_S84_M15_OLDWICK_FOLLOW_RD2.0_2.7_H11_12x9.007
```

| Metric | S130 |
|---|---:|
| Avg $/day | 1239.3009 |
| Min $/day | 1206.5335 |
| Min PF | 9.61930 |
| Max losing-day streak | 3 |
| Worst day | -999.90930 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10525 |

## New Leg

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin2_rd2.7_hfrom13_hbefore14
```

- Base generator: S84 old-wick follow (config index 28 เดิม)
- Mode: inverse raw, TF M15
- Post-filter: `2.0 <= risk_distance <= 2.7`
- Time filter: `13 <= fill_hour < 14` BKK
- Raw trades: 11/15/18/23 ที่ 90/120/150/180d — floor bind ปกติ
- Leg equity stats: lot_max 0.03, leg DD 1.41%, skipped 3

## New Champion

```text
S131 = S130 + INV_S84_M15_OLDWICK_FOLLOW_RD2.0_2.7_H13_14x27.442
```

| Metric | S131 |
|---|---:|
| Avg $/day | 1241.8181 |
| Min $/day | 1208.5855 |
| Min PF | 9.65583 |
| Max losing-day streak | 3 |
| Worst day | -999.90930 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10528 |

Per-window exact from `s131_s84_inv_rdmin20_rd27_h13_14_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1237.1338 | 11.32585 | 2 | -975.54402 | 11 |
| 120 | 1239.3417 | 11.05490 | 2 | -965.68174 | 15 |
| 150 | 1282.2115 | 10.80423 | 3 | -999.90896 | 18 |
| 180 | 1208.5855 | 9.65583 | 3 | -999.90930 | 23 |

## Weight Threshold

`s131_s84_inv_rdmin20_rd27_h13_14_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 27.442 | highest 0.001-step weight that passes `-999.91` |
| 27.443 | fails `-999.91` |

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
- `s131_s84_inv_rdmin20_rd27_h13_14_target28_probe.csv`
- `s131_s84_inv_rdmin20_rd27_h13_14_target28_fine.csv`
- `s131_s84_inv_rdmin20_rd27_h13_14_target28_ultrafine.csv`
- `s131_s84_inv_rdmin20_rd27_h13_14_daily.csv`
- `create_ambfix_audit.md` + `s130_ambfix_ladder_summary.csv` (audit)

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S131 uses `s130_s84_inv_rdmin20_rd27_h11_12_daily.csv` as the base.
- Leg sizing ผ่าน `simulate_equity_substream(raw, cfg, START_EQUITY=1000)` เช่นเดิม
- S84 detection uses closed bar `j`; fill from `j+1`; filters ใช้ข้อมูล ณ ตอนเข้าไม้
- ไม่มี look-ahead เชิงกลไก — แต่มี **intrabar resolution bias** ระดับ framework
  (ดู `create_ambfix_audit.md`) ซึ่งคง convention เดิมไว้ตามคำสั่งผู้ใช้

## Verdict

Found new champion under the original convention:

```text
S131 = S130 + INV_S84_M15_OLDWICK_FOLLOW_RD2.0_2.7_H13_14x27.442
```

This improves avg $/day (1239.30 → 1241.82) and min $/day (1206.53 → 1208.59) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors.
Continue with S132 search using S131 as the new baseline — และแนะนำให้พิจารณาเปิด
track คู่ขนาน "ambfix ladder" ที่หา leg ซึ่งรอดใต้ resolution จริง (แบบ P13/P16).
