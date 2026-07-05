# AF41 — Ambfix Ladder: Inverse S84 cfg889 RD 2.7-3.4 H16

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 889: `S84_M15_lb48_rw0.25_wb1_eat0.12_fail0.03_op0_mb0.12_mr0.35_rr_revisit_sl0.2_rr1.2`

## Baseline

```text
AF40 = AF39 + AMBFIX_INV_S84c889_RD2.0_2.7_H18x168.714
```

| Metric | AF40 |
|---|---:|
| Avg $/day | 1642.8742 |
| Min $/day | 1573.3471 |
| Min PF | 7.85513 |
| Max streak | 3 |
| Worst day | -999.90966 |

## Search (sweep2 cfg889 บน AF40 base — เฉพาะ legs bind จริง)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **inverse** | **2.7-3.4** | **H16** | **105** | **1652.98** | **1586.74** | ✅ ผู้ชนะ |
| direct | 5.0-7.0 | H15 | 30 | 1651.14 | 1577.91 | candidate AF42 (29 ไม้ เนื้อแน่น) |
| direct | 3.4-4.0 | H16 | 445 | 1651.13 | 1573.69 | candidate |

## New Leg

```text
AMBFIX_INV_S84c889_RD2.7_3.4_H16 — inverse, `2.7 <= risk_distance <= 3.4`, fill_hour == 16 BKK
```

- Raw trades: 2/3/4/6 ที่ 90/120/150/180d — ⚠️ บาง ระบุเป็นคำเตือน
- Leg stats: lot_max 0.02, DD 0.77%, skipped 0

## New Champion

```text
AF41 = AF40 + AMBFIX_INV_S84c889_RD2.7_3.4_H16x106.536
```

| Metric | AF41 |
|---|---:|
| Avg $/day | 1653.1307 |
| Min $/day | 1586.9363 |
| Min PF | 8.10790 |
| Max losing-day streak | 3 |
| Worst day | -999.90966 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1586.9363 | 8.10790 | 3 | -999.90945 | 2 |
| 120 | 1701.8724 | 9.84863 | 3 | -999.90966 | 3 |
| 150 | 1725.3701 | 10.43739 | 3 | -999.90921 | 4 |
| 180 | 1598.3440 | 9.32623 | 3 | -999.90946 | 6 |

## Weight Threshold

`af41_ambfix_c889_inv_rdmin27_rd34_h16_probe.csv`: x106.536 ผ่าน / x106.537 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF41 = AF40 + AMBFIX_INV_S84c889_RD2.7_3.4_H16x106.536
```

ชนะ AF40 ทั้ง avg (1642.87 → 1653.13) และ min (1573.35 → 1586.94) — เหลือ ~$347
ถึงเป้า avg $2000 — ไล่ AF42 ต่อ (DIR 5.0-7.0 H15 29 ไม้ / DIR 3.4-4.0 H16)
