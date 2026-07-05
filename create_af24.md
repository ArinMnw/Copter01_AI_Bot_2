# AF24 — 🎯 Ambfix Ladder ทุก window ≥ $1000: Direct S84 cfg6017 All-RD H12

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 6017: `S84_M30_lb48_rw0.35_wb1_eat0.12_fail0.08_op1_mb0.06_mr0.25_mid_revisit_sl0.2_rr1.2`

## 🎯 Milestone

**AF24 คือ champion แรกของ ambfix ladder ที่ min $/day ≥ $1000** — ทุก window
(90/120/150/180d) อยู่เหนือ $1008/วัน **เป้า $1000/วัน สำเร็จสมบูรณ์ทั้ง avg และ min
ภายใต้กติกาซื่อสัตย์** (M1-replay + pessimistic fallback)
จาก S88 base 481.62/449.12 → 1038.76/1008.80 ใน 24 ขั้น

## Baseline

```text
AF23 = AF22 + AMBFIX_INV_S84c6017_RD5.0_7.0_H16x344.837
```

| Metric | AF23 |
|---|---:|
| Avg $/day | 1017.9378 |
| Min $/day | 995.1048 |
| Min PF | 6.89752 |
| Max streak | 3 |
| Worst day | -999.90965 |

## Search (sweep2 cfg6017 บน AF23 base — ข้าม 1-ไม้ degenerate ชน cap 3 ตัว)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **all (ไม่กรอง RD)** | **H12** | **22** | **1037.10** | **1007.71** | ✅ ผู้ชนะ — leg เนื้อแน่นสุดของ cfg6017 (46 ไม้@180d) |
| direct | 4.0-5.0 | H12 | 516 | 1035.21 | 997.08 | subset ของผู้ชนะ |

## New Leg

```text
AMBFIX_DIR_S84c6017_ALL_H12 — direct, ไม่กรอง risk_distance, fill_hour == 12 BKK
```

- Raw trades: 24/34/41/46 ที่ 90/120/150/180d — **หนาแน่นที่สุดตั้งแต่เริ่ม AF ladder**
- Leg stats: lot_max 0.01, DD 9.11%, skipped 10

## New Champion

```text
AF24 = AF23 + AMBFIX_DIR_S84c6017_ALL_H12x23.911
```

| Metric | AF24 |
|---|---:|
| Avg $/day | 1038.7604 |
| Min $/day | 1008.8045 |
| Min PF | 6.76284 |
| Max losing-day streak | 3 |
| Worst day | -999.90965 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1052.6209 | 6.76284 | 2 | -999.90777 | 24 |
| 120 | 1073.8155 | 7.69007 | 3 | -999.90805 | 34 |
| 150 | 1019.8006 | 6.78155 | 3 | -999.90965 | 41 |
| 180 | 1008.8045 | 7.42792 | 3 | -999.90946 | 46 |

## Weight Threshold

`af24_ambfix_c6017_dir_all_h12_probe.csv`: x23.911 ผ่าน / x23.912 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## ⚠️ คำเตือน

ตัวเลขยังเป็น in-sample selection — ต้องผ่าน walk-forward / out-of-sample ก่อน
พิจารณา deploy เสมอ

## Verdict

```text
AF24 = AF23 + AMBFIX_DIR_S84c6017_ALL_H12x23.911
```

ชนะ AF23 ทั้ง avg (1017.94 → 1038.76) และ min (995.10 → 1008.80) และ**ปิดเป้า
$1000/วัน สมบูรณ์ทั้ง avg+min ภายใต้กติกาซื่อสัตย์** — เป้าถัดไป $1500/วัน
(คิว: cfg5505/4369/889 + s86 family screen)
