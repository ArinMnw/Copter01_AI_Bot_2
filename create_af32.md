# AF32 — Ambfix Ladder: Direct S84 cfg889 RD 2.7-3.4 H9 (เปิด config ที่ 5)

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 889: `S84_M15_lb48_rw0.25_wb1_eat0.12_fail0.03_op0_mb0.12_mr0.35_rr_revisit_sl0.2_rr1.2`
(screen: inv_sum +791.8, n=1972; stream ambiguity 51 ไม้)

## Baseline

```text
AF31 = AF30 + AMBFIX_INV_S84c3057_RD3.4_4.0_H11x321.025
```

| Metric | AF31 |
|---|---:|
| Avg $/day | 1383.3074 |
| Min $/day | 1326.2080 |
| Min PF | 7.66922 |
| Max streak | 3 |
| Worst day | -999.90965 |

## Search (sweep2 cfg889 บน AF31 base)

| Mode | Band | Hour | Best w | avg | min | หมายเหตุ |
|---|---|---|---:|---:|---:|---|
| inverse | 4.0-5.0 | H22 | ชน cap 4000 | 1939.69 | 1716.65 | ❌ degenerate (4 ไม้ ชนะหมด) — ข้ามตามกติกา |
| **direct** | **2.7-3.4** | **H9** | **490** | **1448.70** | **1375.81** | ✅ ผู้ชนะ (floor bind ปกติ x491.628) |
| inverse | 3.4-4.0 | H19 | cap | — | — | ❌ degenerate |

## New Leg

```text
AMBFIX_DIR_S84c889_RD2.7_3.4_H9 — direct, `2.7 <= risk_distance <= 3.4`, fill_hour == 9 BKK
```

- Raw trades: 5/6/6/6 ที่ 90/120/150/180d
- Leg stats: lot_max 0.02, DD 0.36%, skipped 0

## New Champion

```text
AF32 = AF31 + AMBFIX_DIR_S84c889_RD2.7_3.4_H9x491.628
```

| Metric | AF32 |
|---|---:|
| Avg $/day | 1448.9219 |
| Min $/day | 1375.9717 |
| Min PF | 7.55671 |
| Max losing-day streak | 3 |
| Worst day | -999.90965 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1457.3997 | 7.55671 | 3 | -999.90820 | 5 |
| 120 | 1494.1584 | 9.17375 | 3 | -999.90805 | 6 |
| 150 | 1468.1580 | 9.41701 | 3 | -999.90965 | 6 |
| 180 | 1375.9717 | 8.82736 | 3 | -999.90946 | 6 |

## Weight Threshold

`af32_ambfix_c889_dir_rdmin27_rd34_h9_probe.csv`: x491.628 ผ่าน / x491.629 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF32 = AF31 + AMBFIX_DIR_S84c889_RD2.7_3.4_H9x491.628
```

ชนะ AF31 ทั้ง avg (1383.31 → 1448.92) และ min (1326.21 → 1375.97) — เหลือ ~$51
ถึงเป้า $1500 (avg)
