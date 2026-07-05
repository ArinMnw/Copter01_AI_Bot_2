# AF37 — Ambfix Ladder: Direct S84 cfg889 RD 2.7-3.4 H18

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 889: `S84_M15_lb48_rw0.25_wb1_eat0.12_fail0.03_op0_mb0.12_mr0.35_rr_revisit_sl0.2_rr1.2`

## Baseline

```text
AF36 = AF35 + AMBFIX_DIR_S84c889_RD4.0_5.0_H17x215.498
```

| Metric | AF36 |
|---|---:|
| Avg $/day | 1533.5978 |
| Min $/day | 1471.5065 |
| Min PF | 7.82026 |
| Max streak | 3 |
| Worst day | -999.90946 |

## New Leg

```text
AMBFIX_DIR_S84c889_RD2.7_3.4_H18 — direct, `2.7 <= risk_distance <= 3.4`, fill_hour == 18 BKK
```

- Raw trades: 2/3/4/5 ที่ 90/120/150/180d — ⚠️ บาง ระบุเป็นคำเตือน
- Leg stats: lot_max 0.02, DD 0.70%, skipped 0
- หมายเหตุขั้นตอน: build ครั้งแรกตั้ง w-hi=200 แล้วผ่านทันที (ชนขอบช่วงค้น) จึงขยาย
  ช่วงหาขอบจริงด้วย sweep ละเอียดก่อน rebuild — threshold จริง x434.774

## New Champion

```text
AF37 = AF36 + AMBFIX_DIR_S84c889_RD2.7_3.4_H18x434.774
```

| Metric | AF37 |
|---|---:|
| Avg $/day | 1557.9077 |
| Min $/day | 1494.6944 |
| Min PF | 7.88310 |
| Max losing-day streak | 3 |
| Worst day | -999.90966 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1534.5385 | 7.88310 | 3 | -999.90945 | 2 |
| 120 | 1596.5118 | 9.52166 | 3 | -999.90966 | 3 |
| 150 | 1605.8863 | 10.35873 | 3 | -999.90921 | 4 |
| 180 | 1494.6944 | 9.27411 | 3 | -999.90946 | 5 |

## Weight Threshold

`af37_ambfix_c889_dir_rdmin27_rd34_h18_probe.csv`: x434.774 ผ่าน / x434.775 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF37 = AF36 + AMBFIX_DIR_S84c889_RD2.7_3.4_H18x434.774
```

ชนะ AF36 ทั้ง avg (1533.60 → 1557.91) และ min (1471.51 → 1494.69) — ไล่ AF38 ต่อ
(INV c889 2.7-3.4 H16 คิวถัดไป) เป้า $2000
