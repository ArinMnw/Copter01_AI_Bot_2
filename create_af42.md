# AF42 — Ambfix Ladder: Direct S84 cfg889 RD 5.0-7.0 H15

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 889: `S84_M15_lb48_rw0.25_wb1_eat0.12_fail0.03_op0_mb0.12_mr0.35_rr_revisit_sl0.2_rr1.2`

## Baseline

```text
AF41 = AF40 + AMBFIX_INV_S84c889_RD2.7_3.4_H16x106.536
```

| Metric | AF41 |
|---|---:|
| Avg $/day | 1653.1307 |
| Min $/day | 1586.9363 |
| Min PF | 8.10790 |
| Max streak | 3 |
| Worst day | -999.90966 |

## New Leg

```text
AMBFIX_DIR_S84c889_RD5.0_7.0_H15 — direct, `5.0 <= risk_distance <= 7.0`, fill_hour == 15 BKK
```

- Raw trades: 14/20/27/29 ที่ 90/120/150/180d — เนื้อแน่น
- Leg stats: lot_max 0.01, DD 1.35%, skipped 0
- หมายเหตุ: filter รูปเดียวกับ AF8 แต่คนละ config (AF8 = config 28) — stream คนละเส้น
  ไม่ใช่ re-weight

## New Champion

```text
AF42 = AF41 + AMBFIX_DIR_S84c889_RD5.0_7.0_H15x32.734
```

| Metric | AF42 |
|---|---:|
| Avg $/day | 1662.1532 |
| Min $/day | 1591.9192 |
| Min PF | 8.28459 |
| Max losing-day streak | 3 |
| Worst day | -999.90966 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1591.9192 | 8.28459 | 3 | -999.90945 | 14 |
| 120 | 1710.2823 | 9.99224 | 3 | -999.90966 | 20 |
| 150 | 1736.2378 | 10.70844 | 3 | -999.90921 | 27 |
| 180 | 1610.1737 | 9.57991 | 3 | -999.90946 | 29 |

## Weight Threshold

`af42_ambfix_c889_dir_rdmin50_rd70_h15_probe.csv`: x32.734 ผ่าน / x32.735 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF42 = AF41 + AMBFIX_DIR_S84c889_RD5.0_7.0_H15x32.734
```

ชนะ AF41 ทั้ง avg (1653.13 → 1662.15) และ min (1586.94 → 1591.92) — เหลือ ~$338
ถึงเป้า avg $2000 — ไล่ AF43 ต่อ
