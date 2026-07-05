# AF36 — Ambfix Ladder: Direct S84 cfg889 RD 4.0-5.0 H17

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 889: `S84_M15_lb48_rw0.25_wb1_eat0.12_fail0.03_op0_mb0.12_mr0.35_rr_revisit_sl0.2_rr1.2`

## Baseline

```text
AF35 = AF34 + AMBFIX_DIR_S84c889_RD4.0_5.0_H19x70.685
```

| Metric | AF35 |
|---|---:|
| Avg $/day | 1522.2477 |
| Min $/day | 1454.4462 |
| Min PF | 7.78859 |
| Max streak | 3 |
| Worst day | -999.90965 |

## Search (sweep2 cfg889 บน AF35 base — เฉพาะ legs bind จริง)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **4.0-5.0** | **H17** | **214** | **1533.52** | **1471.39** | ✅ ผู้ชนะ (19 ไม้ เนื้อแน่นสุดของ c889) |
| direct | 2.7-3.4 | H18 | 192 | 1532.98 | 1464.69 | candidate AF37 |
| inverse | 2.7-3.4 | H16 | 106 | 1532.45 | 1460.31 | candidate |

## New Leg

```text
AMBFIX_DIR_S84c889_RD4.0_5.0_H17 — direct, `4.0 <= risk_distance <= 5.0`, fill_hour == 17 BKK
```

- Raw trades: 9/12/16/19 ที่ 90/120/150/180d
- Leg stats: lot_max 0.01, DD 1.33%, skipped 1

## New Champion

```text
AF36 = AF35 + AMBFIX_DIR_S84c889_RD4.0_5.0_H17x215.498
```

| Metric | AF36 |
|---|---:|
| Avg $/day | 1533.5978 |
| Min $/day | 1471.5065 |
| Min PF | 7.82026 |
| Max losing-day streak | 3 |
| Worst day | -999.90946 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1520.5291 | 7.82026 | 3 | -999.90945 | 9 |
| 120 | 1574.5557 | 9.79567 | 3 | -999.90852 | 12 |
| 150 | 1567.8001 | 10.24932 | 3 | -999.90921 | 16 |
| 180 | 1471.5065 | 9.44214 | 3 | -999.90946 | 19 |

## Weight Threshold

`af36_ambfix_c889_dir_rdmin40_rd50_h17_probe.csv`: x215.498 ผ่าน / x215.499 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF36 = AF35 + AMBFIX_DIR_S84c889_RD4.0_5.0_H17x215.498
```

ชนะ AF35 ทั้ง avg (1522.25 → 1533.60) และ min (1454.45 → 1471.51) — ไล่ AF37 ต่อ
(DIR c889 2.7-3.4 H18 / INV 2.7-3.4 H16) เป้า $2000
