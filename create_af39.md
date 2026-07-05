# AF39 — Ambfix Ladder: Direct S84 cfg889 RD 2.7-3.4 H20

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 889: `S84_M15_lb48_rw0.25_wb1_eat0.12_fail0.03_op0_mb0.12_mr0.35_rr_revisit_sl0.2_rr1.2`

## Baseline

```text
AF38 = AF37 + AMBFIX_DIR_S84c889_RD2.7_3.4_H11x888.785
```

| Metric | AF38 |
|---|---:|
| Avg $/day | 1609.5190 |
| Min $/day | 1536.3160 |
| Min PF | 7.88157 |
| Max streak | 3 |
| Worst day | -999.90966 |

## Search (sweep2 cfg889 บน AF38 base — เฉพาะ legs bind จริง)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **2.7-3.4** | **H20** | **285** | **1631.61** | **1558.67** | ✅ ผู้ชนะ |
| inverse | 2.0-2.7 | H18 | 165 | 1620.41 | 1550.54 | candidate AF40 (9 ไม้) |
| direct | 1.3-2.0 | H13 | 210 | 1619.64 | 1550.53 | candidate |

## New Leg

```text
AMBFIX_DIR_S84c889_RD2.7_3.4_H20 — direct, `2.7 <= risk_distance <= 3.4`, fill_hour == 20 BKK
```

- Raw trades: 3/3/4/4 ที่ 90/120/150/180d — ⚠️ บาง ระบุเป็นคำเตือน
- Leg stats: lot_max 0.02, DD 0.61%, skipped 0

## New Champion

```text
AF39 = AF38 + AMBFIX_DIR_S84c889_RD2.7_3.4_H20x286.625
```

| Metric | AF39 |
|---|---:|
| Avg $/day | 1631.7396 |
| Min $/day | 1558.8002 |
| Min PF | 7.65180 |
| Max losing-day streak | 3 |
| Worst day | -999.90966 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1558.8002 | 7.65180 | 3 | -999.90945 | 3 |
| 120 | 1669.2202 | 9.18206 | 3 | -999.90966 | 3 |
| 150 | 1714.0811 | 10.48673 | 3 | -999.90921 | 4 |
| 180 | 1584.8568 | 9.42540 | 3 | -999.90946 | 4 |

## Weight Threshold

`af39_ambfix_c889_dir_rdmin27_rd34_h20_probe.csv`: x286.625 ผ่าน / x286.626 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF39 = AF38 + AMBFIX_DIR_S84c889_RD2.7_3.4_H20x286.625
```

ชนะ AF38 ทั้ง avg (1609.52 → 1631.74) และ min (1536.32 → 1558.80) — เหลือ ~$368
ถึงเป้า avg $2000 — ไล่ AF40 ต่อ
