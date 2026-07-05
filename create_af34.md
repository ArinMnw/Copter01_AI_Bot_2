# AF34 — 🎯 Ambfix Ladder ทะลุ $1500/วัน: Inverse S84 cfg889 RD 2.7-3.4 H13

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 889: `S84_M15_lb48_rw0.25_wb1_eat0.12_fail0.03_op0_mb0.12_mr0.35_rr_revisit_sl0.2_rr1.2`

## 🎯 Milestone

**AF34 คือ champion แรกของ ambfix ladder ที่ avg $/day ≥ $1500** — จาก S88 base
$481.62 → $1,504.91 ใน 34 ขั้น ภายใต้กติกาซื่อสัตย์ (M1-replay + pessimistic)
เป้าถัดไป: min ≥ $1500 → $2000

## Baseline

```text
AF33 = AF32 + AMBFIX_DIR_S84c889_RD3.4_4.0_H13x437.129
```

| Metric | AF33 |
|---|---:|
| Avg $/day | 1477.7093 |
| Min $/day | 1406.5464 |
| Min PF | 7.72936 |
| Max streak | 3 |
| Worst day | -999.90965 |

## Search (sweep2 cfg889 บน AF33 base — เฉพาะ legs ที่ bind จริง)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **inverse** | **2.7-3.4** | **H13** | **272** | **1504.73** | **1439.19** | ✅ ผู้ชนะ |
| direct | 4.0-5.0 | H19 | 70 | 1494.88 | 1421.44 | candidate AF35 (13 ไม้) |
| direct | 4.0-5.0 | H17 | 214 | 1488.98 | 1423.49 | candidate (19 ไม้ เนื้อแน่น) |

## New Leg

```text
AMBFIX_INV_S84c889_RD2.7_3.4_H13 — inverse, `2.7 <= risk_distance <= 3.4`, fill_hour == 13 BKK
```

- Raw trades: 1/2/5/6 ที่ 90/120/150/180d — ⚠️ บาง ระบุเป็นคำเตือน
- Leg stats: lot_max 0.02, DD 0.74%, skipped 0

## New Champion

```text
AF34 = AF33 + AMBFIX_INV_S84c889_RD2.7_3.4_H13x273.830
```

| Metric | AF34 |
|---|---:|
| Avg $/day | 1504.9082 |
| Min $/day | 1439.4060 |
| Min PF | 7.81476 |
| Max losing-day streak | 3 |
| Worst day | -999.90965 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1495.5698 | 7.81476 | 3 | -999.90820 | 1 |
| 120 | 1551.2125 | 9.88355 | 3 | -999.90805 | 2 |
| 150 | 1533.4446 | 9.55808 | 3 | -999.90965 | 5 |
| 180 | 1439.4060 | 9.11101 | 3 | -999.90946 | 6 |

## Weight Threshold

`af34_ambfix_c889_inv_rdmin27_rd34_h13_probe.csv`: x273.830 ผ่าน / x273.831 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## ⚠️ คำเตือน

ตัวเลขเป็น in-sample selection — ต้องผ่าน walk-forward / out-of-sample validation
ก่อนพิจารณา deploy เสมอ

## Verdict

```text
AF34 = AF33 + AMBFIX_INV_S84c889_RD2.7_3.4_H13x273.830
```

ชนะ AF33 ทั้ง avg (1477.71 → 1504.91) และ min (1406.55 → 1439.41) และ**ทะลุเป้า
$1500/วัน (avg)** — ไล่ AF35 ต่อ เป้าถัดไป min ≥ $1500 → $2000
