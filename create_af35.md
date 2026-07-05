# AF35 — Ambfix Ladder: Direct S84 cfg889 RD 4.0-5.0 H19

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 889: `S84_M15_lb48_rw0.25_wb1_eat0.12_fail0.03_op0_mb0.12_mr0.35_rr_revisit_sl0.2_rr1.2`

## Baseline

```text
AF34 = AF33 + AMBFIX_INV_S84c889_RD2.7_3.4_H13x273.830
```

| Metric | AF34 |
|---|---:|
| Avg $/day | 1504.9082 |
| Min $/day | 1439.4060 |
| Min PF | 7.81476 |
| Max streak | 3 |
| Worst day | -999.90965 |

## Search (sweep2 cfg889 บน AF34 base — เฉพาะ legs bind จริง)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **4.0-5.0** | **H19** | **70** | **1522.08** | **1454.30** | ✅ ผู้ชนะ (13 ไม้) |
| direct | 4.0-5.0 | H17 | 214 | 1516.18 | 1456.35 | candidate AF36 (19 ไม้) |
| direct | 2.7-3.4 | H18 | 192 | 1515.64 | 1449.65 | candidate |

## New Leg

```text
AMBFIX_DIR_S84c889_RD4.0_5.0_H19 — direct, `4.0 <= risk_distance <= 5.0`, fill_hour == 19 BKK
```

- Raw trades: 8/9/12/13 ที่ 90/120/150/180d
- Leg stats: lot_max 0.01, DD 0.50%, skipped 0

## New Champion

```text
AF35 = AF34 + AMBFIX_DIR_S84c889_RD4.0_5.0_H19x70.685
```

| Metric | AF35 |
|---|---:|
| Avg $/day | 1522.2477 |
| Min $/day | 1454.4462 |
| Min PF | 7.78859 |
| Max losing-day streak | 3 |
| Worst day | -999.90965 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1513.1782 | 7.78859 | 3 | -999.90945 | 8 |
| 120 | 1567.5879 | 9.84662 | 3 | -999.90805 | 9 |
| 150 | 1553.7783 | 9.57281 | 3 | -999.90965 | 12 |
| 180 | 1454.4462 | 9.03172 | 3 | -999.90946 | 13 |

## Weight Threshold

`af35_ambfix_c889_dir_rdmin40_rd50_h19_probe.csv`: x70.685 ผ่าน / x70.686 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF35 = AF34 + AMBFIX_DIR_S84c889_RD4.0_5.0_H19x70.685
```

ชนะ AF34 ทั้ง avg (1504.91 → 1522.25) และ min (1439.41 → 1454.45) — ไล่ AF36 ต่อ
(DIR c889 4.0-5.0 H17 / 2.7-3.4 H18) เป้า $2000
