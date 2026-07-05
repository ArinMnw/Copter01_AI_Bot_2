# AF33 — Ambfix Ladder: Direct S84 cfg889 RD 3.4-4.0 H13

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 889: `S84_M15_lb48_rw0.25_wb1_eat0.12_fail0.03_op0_mb0.12_mr0.35_rr_revisit_sl0.2_rr1.2`

## Baseline

```text
AF32 = AF31 + AMBFIX_DIR_S84c889_RD2.7_3.4_H9x491.628
```

| Metric | AF32 |
|---|---:|
| Avg $/day | 1448.9219 |
| Min $/day | 1375.9717 |
| Min PF | 7.55671 |
| Max streak | 3 |
| Worst day | -999.90965 |

## Search (sweep2 cfg889 บน AF32 base — degenerate ชน cap ถูกข้ามทั้งหมด
คัดเฉพาะ legs ที่ floor bind จริง < cap)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **3.4-4.0** | **H13** | **436** | **1477.64** | **1406.47** | ✅ ผู้ชนะ |
| inverse | 2.7-3.4 | H13 | 272 | 1475.94 | 1408.61 | candidate AF34 |
| direct | 4.0-5.0 | H17 | 214 | 1460.19 | 1392.91 | candidate (19 ไม้ เนื้อแน่น) |

## New Leg

```text
AMBFIX_DIR_S84c889_RD3.4_4.0_H13 — direct, `3.4 <= risk_distance <= 4.0`, fill_hour == 13 BKK
```

- Raw trades: 3/4/5/7 ที่ 90/120/150/180d
- Leg stats: lot_max 0.01, DD 0.41%, skipped 0

## New Champion

```text
AF33 = AF32 + AMBFIX_DIR_S84c889_RD3.4_4.0_H13x437.129
```

| Metric | AF33 |
|---|---:|
| Avg $/day | 1477.7093 |
| Min $/day | 1406.5464 |
| Min PF | 7.72936 |
| Max losing-day streak | 3 |
| Worst day | -999.90965 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1476.8276 | 7.72936 | 3 | -999.90820 | 3 |
| 120 | 1523.3732 | 9.72412 | 3 | -999.90805 | 4 |
| 150 | 1504.0900 | 9.71862 | 3 | -999.90965 | 5 |
| 180 | 1406.5464 | 9.14872 | 3 | -999.90946 | 7 |

## Weight Threshold

`af33_ambfix_c889_dir_rdmin34_rd40_h13_probe.csv`: x437.129 ผ่าน / x437.130 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF33 = AF32 + AMBFIX_DIR_S84c889_RD3.4_4.0_H13x437.129
```

ชนะ AF32 ทั้ง avg (1448.92 → 1477.71) และ min (1375.97 → 1406.55) — เหลือ ~$22
ถึงเป้า $1500 (avg)
