# AF40 — Ambfix Ladder: Inverse S84 cfg889 RD 2.0-2.7 H18

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 889: `S84_M15_lb48_rw0.25_wb1_eat0.12_fail0.03_op0_mb0.12_mr0.35_rr_revisit_sl0.2_rr1.2`

## Baseline

```text
AF39 = AF38 + AMBFIX_DIR_S84c889_RD2.7_3.4_H20x286.625
```

| Metric | AF39 |
|---|---:|
| Avg $/day | 1631.7396 |
| Min $/day | 1558.8002 |
| Min PF | 7.65180 |
| Max streak | 3 |
| Worst day | -999.90966 |

## Search (sweep2 cfg889 บน AF39 base — เฉพาะ legs bind จริง)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **inverse** | **2.0-2.7** | **H18** | **165** | **1642.63** | **1573.03** | ✅ ผู้ชนะ (9 ไม้) |
| direct | 1.3-2.0 | H13 | 210 | 1641.86 | 1573.01 | candidate AF41 |
| inverse | 2.7-3.4 | H16 | 105 | 1641.85 | 1572.19 | candidate |

## New Leg

```text
AMBFIX_INV_S84c889_RD2.0_2.7_H18 — inverse, `2.0 <= risk_distance <= 2.7`, fill_hour == 18 BKK
```

- Raw trades: 4/5/8/9 ที่ 90/120/150/180d
- Leg stats: lot_max 0.02, DD 1.30%, skipped 0

## New Champion

```text
AF40 = AF39 + AMBFIX_INV_S84c889_RD2.0_2.7_H18x168.714
```

| Metric | AF40 |
|---|---:|
| Avg $/day | 1642.8742 |
| Min $/day | 1573.3471 |
| Min PF | 7.85513 |
| Max losing-day streak | 3 |
| Worst day | -999.90966 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1573.3471 | 7.85513 | 3 | -999.90945 | 4 |
| 120 | 1686.8508 | 9.45663 | 3 | -999.90966 | 5 |
| 150 | 1718.8501 | 10.34375 | 3 | -999.90921 | 8 |
| 180 | 1592.4490 | 9.36763 | 3 | -999.90946 | 9 |

## Weight Threshold

`af40_ambfix_c889_inv_rdmin20_rd27_h18_probe.csv`: x168.714 ผ่าน / x168.715 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF40 = AF39 + AMBFIX_INV_S84c889_RD2.0_2.7_H18x168.714
```

ชนะ AF39 ทั้ง avg (1631.74 → 1642.87) และ min (1558.80 → 1573.35) — เหลือ ~$357
ถึงเป้า avg $2000 — ไล่ AF41 ต่อ
