# AF38 — Ambfix Ladder: Direct S84 cfg889 RD 2.7-3.4 H11

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 889: `S84_M15_lb48_rw0.25_wb1_eat0.12_fail0.03_op0_mb0.12_mr0.35_rr_revisit_sl0.2_rr1.2`

## Baseline

```text
AF37 = AF36 + AMBFIX_DIR_S84c889_RD2.7_3.4_H18x434.774
```

| Metric | AF37 |
|---|---:|
| Avg $/day | 1557.9077 |
| Min $/day | 1494.6944 |
| Min PF | 7.88310 |
| Max streak | 3 |
| Worst day | -999.90966 |

## Search (sweep2 cfg889 บน AF37 base, grid ถึง 2000 — เฉพาะ legs bind จริง)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **2.7-3.4** | **H11** | **885** | **1609.30** | **1536.31** | ✅ ผู้ชนะ |
| direct | 2.7-3.4 | H20 | 285 | 1580.00 | 1517.08 | candidate AF39 |
| inverse | 4.0-5.0 | H14 | 375 | 1568.21 | 1516.26 | candidate (14 ไม้) |

## New Leg

```text
AMBFIX_DIR_S84c889_RD2.7_3.4_H11 — direct, `2.7 <= risk_distance <= 3.4`, fill_hour == 11 BKK
```

- Raw trades: 2/3/4/5 ที่ 90/120/150/180d — ⚠️ บาง ระบุเป็นคำเตือน
- Leg stats: lot_max 0.02, DD 0.59%, skipped 0

## New Champion

```text
AF38 = AF37 + AMBFIX_DIR_S84c889_RD2.7_3.4_H11x888.785
```

| Metric | AF38 |
|---|---:|
| Avg $/day | 1609.5190 |
| Min $/day | 1536.3160 |
| Min PF | 7.88157 |
| Max losing-day streak | 3 |
| Worst day | -999.90966 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1536.3160 | 7.88157 | 3 | -999.90945 | 2 |
| 120 | 1652.3571 | 9.44418 | 3 | -999.90966 | 3 |
| 150 | 1687.0620 | 10.68563 | 3 | -999.90921 | 4 |
| 180 | 1562.3409 | 9.55526 | 3 | -999.90946 | 5 |

## Weight Threshold

`af38_ambfix_c889_dir_rdmin27_rd34_h11_probe.csv`: x888.785 ผ่าน / x888.786 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF38 = AF37 + AMBFIX_DIR_S84c889_RD2.7_3.4_H11x888.785
```

ชนะ AF37 ทั้ง avg (1557.91 → 1609.52) และ min (1494.69 → 1536.32) — **min ทะลุ
$1500 แล้ว** เหลือ ~$390 ถึงเป้า avg $2000 — ไล่ AF39 ต่อ
